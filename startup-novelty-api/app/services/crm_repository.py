from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from app.models import (
    CRMCompany,
    CRMCompanyCreate,
    CRMCountBucket,
    CRMPitch,
    CRMPitchCreate,
    CRMSummaryResponse,
)


class CRMRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    website TEXT,
                    sector TEXT NOT NULL DEFAULT '',
                    country TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    founder_names_json TEXT NOT NULL DEFAULT '[]',
                    contact_email TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crm_pitches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    pitch_date TEXT NOT NULL,
                    deal_status TEXT NOT NULL,
                    funding_status TEXT NOT NULL,
                    round_name TEXT NOT NULL DEFAULT '',
                    amount_requested_usd REAL,
                    source TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(company_id) REFERENCES crm_companies(id)
                )
                """
            )
            connection.commit()

    def upsert_company(self, company: CRMCompanyCreate) -> CRMCompany:
        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = self._find_existing_company(connection, company.company_name, company.website)
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO crm_companies (
                        company_name, website, sector, country, description,
                        founder_names_json, contact_email, notes, keywords_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company.company_name,
                        company.website,
                        company.sector,
                        company.country,
                        company.description,
                        json.dumps(company.founder_names),
                        company.contact_email,
                        company.notes,
                        json.dumps(company.keywords),
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                connection.commit()
                company_id = int(cursor.lastrowid)
            else:
                company_id = int(existing["id"])
                merged = self._merge_company(existing, company)
                connection.execute(
                    """
                    UPDATE crm_companies
                    SET company_name = ?, website = ?, sector = ?, country = ?, description = ?,
                        founder_names_json = ?, contact_email = ?, notes = ?, keywords_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        merged.company_name,
                        merged.website,
                        merged.sector,
                        merged.country,
                        merged.description,
                        json.dumps(merged.founder_names),
                        merged.contact_email,
                        merged.notes,
                        json.dumps(merged.keywords),
                        now.isoformat(),
                        company_id,
                    ),
                )
                connection.commit()

        return self.get_company(company_id)

    def create_pitch(self, pitch: CRMPitchCreate) -> CRMPitch:
        created_at = datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            company = connection.execute(
                "SELECT id FROM crm_companies WHERE id = ?",
                (pitch.company_id,),
            ).fetchone()
            if company is None:
                raise ValueError(f"CRM company {pitch.company_id} was not found.")

            cursor = connection.execute(
                """
                INSERT INTO crm_pitches (
                    company_id, pitch_date, deal_status, funding_status, round_name,
                    amount_requested_usd, source, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pitch.company_id,
                    pitch.pitch_date.isoformat(),
                    pitch.deal_status,
                    pitch.funding_status,
                    pitch.round_name,
                    pitch.amount_requested_usd,
                    pitch.source,
                    pitch.notes,
                    created_at.isoformat(),
                ),
            )
            connection.commit()
            pitch_id = int(cursor.lastrowid)
        return self.get_pitch(pitch_id)

    def record_pitch_for_company(
        self,
        company: CRMCompanyCreate,
        pitch: CRMPitchCreate,
    ) -> tuple[CRMCompany, CRMPitch]:
        saved_company = self.upsert_company(company)
        saved_pitch = self.create_pitch(
            CRMPitchCreate(
                company_id=saved_company.id,
                pitch_date=pitch.pitch_date,
                deal_status=pitch.deal_status,
                funding_status=pitch.funding_status,
                round_name=pitch.round_name,
                amount_requested_usd=pitch.amount_requested_usd,
                source=pitch.source,
                notes=pitch.notes,
            )
        )
        return saved_company, saved_pitch

    def list_companies(self) -> list[CRMCompany]:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, company_name, website, sector, country, description,
                       founder_names_json, contact_email, notes, keywords_json, created_at, updated_at
                FROM crm_companies
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        return [self._row_to_company(row) for row in rows]

    def list_pitches(self) -> list[CRMPitch]:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT p.id, p.company_id, c.company_name, c.website AS company_website,
                       p.pitch_date, p.deal_status, p.funding_status, p.round_name,
                       p.amount_requested_usd, p.source, p.notes, p.created_at
                FROM crm_pitches p
                JOIN crm_companies c ON c.id = p.company_id
                ORDER BY p.pitch_date DESC, p.id DESC
                """
            ).fetchall()
        return [self._row_to_pitch(row) for row in rows]

    def get_summary(self) -> CRMSummaryResponse:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            total_companies = int(connection.execute("SELECT COUNT(*) FROM crm_companies").fetchone()[0])
            total_pitches = int(connection.execute("SELECT COUNT(*) FROM crm_pitches").fetchone()[0])
            deal_rows = connection.execute(
                "SELECT deal_status AS label, COUNT(*) AS count FROM crm_pitches GROUP BY deal_status ORDER BY count DESC"
            ).fetchall()
            funding_rows = connection.execute(
                "SELECT funding_status AS label, COUNT(*) AS count FROM crm_pitches GROUP BY funding_status ORDER BY count DESC"
            ).fetchall()
            month_rows = connection.execute(
                """
                SELECT substr(pitch_date, 1, 7) AS label, COUNT(*) AS count
                FROM crm_pitches
                GROUP BY substr(pitch_date, 1, 7)
                ORDER BY label DESC
                LIMIT 12
                """
            ).fetchall()

        return CRMSummaryResponse(
            total_companies=total_companies,
            total_pitches=total_pitches,
            deal_status_counts=[CRMCountBucket(label=row["label"], count=int(row["count"])) for row in deal_rows],
            funding_status_counts=[CRMCountBucket(label=row["label"], count=int(row["count"])) for row in funding_rows],
            monthly_pitch_counts=[
                CRMCountBucket(label=row["label"], count=int(row["count"])) for row in reversed(month_rows)
            ],
        )

    def get_company(self, company_id: int) -> CRMCompany:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT id, company_name, website, sector, country, description,
                       founder_names_json, contact_email, notes, keywords_json, created_at, updated_at
                FROM crm_companies
                WHERE id = ?
                """,
                (company_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"CRM company {company_id} was not found.")
        return self._row_to_company(row)

    def get_pitch(self, pitch_id: int) -> CRMPitch:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT p.id, p.company_id, c.company_name, c.website AS company_website,
                       p.pitch_date, p.deal_status, p.funding_status, p.round_name,
                       p.amount_requested_usd, p.source, p.notes, p.created_at
                FROM crm_pitches p
                JOIN crm_companies c ON c.id = p.company_id
                WHERE p.id = ?
                """,
                (pitch_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"CRM pitch {pitch_id} was not found.")
        return self._row_to_pitch(row)

    def _find_existing_company(
        self,
        connection: sqlite3.Connection,
        company_name: str,
        website: str | None,
    ) -> sqlite3.Row | None:
        if website:
            row = connection.execute(
                "SELECT * FROM crm_companies WHERE lower(website) = lower(?)",
                (website,),
            ).fetchone()
            if row is not None:
                return row
        return connection.execute(
            "SELECT * FROM crm_companies WHERE lower(company_name) = lower(?)",
            (company_name,),
        ).fetchone()

    def _merge_company(self, existing: sqlite3.Row, company: CRMCompanyCreate) -> CRMCompanyCreate:
        existing_founders = json.loads(existing["founder_names_json"] or "[]")
        existing_keywords = json.loads(existing["keywords_json"] or "[]")
        merged_founders = sorted({name for name in [*existing_founders, *company.founder_names] if name})
        merged_keywords = sorted({keyword for keyword in [*existing_keywords, *company.keywords] if keyword})
        return CRMCompanyCreate(
            company_name=company.company_name or existing["company_name"],
            website=company.website or existing["website"],
            sector=company.sector or existing["sector"],
            country=company.country or existing["country"],
            description=company.description or existing["description"],
            founder_names=merged_founders,
            contact_email=company.contact_email or existing["contact_email"],
            notes=company.notes or existing["notes"],
            keywords=merged_keywords,
        )

    def _row_to_company(self, row: sqlite3.Row) -> CRMCompany:
        return CRMCompany(
            id=int(row["id"]),
            company_name=row["company_name"],
            website=row["website"],
            sector=row["sector"],
            country=row["country"],
            description=row["description"],
            founder_names=json.loads(row["founder_names_json"] or "[]"),
            contact_email=row["contact_email"],
            notes=row["notes"],
            keywords=json.loads(row["keywords_json"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_pitch(self, row: sqlite3.Row) -> CRMPitch:
        return CRMPitch(
            id=int(row["id"]),
            company_id=int(row["company_id"]),
            company_name=row["company_name"],
            company_website=row["company_website"],
            pitch_date=date.fromisoformat(row["pitch_date"]),
            deal_status=row["deal_status"],
            funding_status=row["funding_status"],
            round_name=row["round_name"],
            amount_requested_usd=row["amount_requested_usd"],
            source=row["source"],
            notes=row["notes"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
