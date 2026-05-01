from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models import PortfolioCompany, PortfolioCompanyCreate


class PortfolioRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    website TEXT,
                    sector TEXT NOT NULL DEFAULT '',
                    country TEXT NOT NULL DEFAULT '',
                    thesis TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    keywords_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def add_company(self, company: PortfolioCompanyCreate) -> PortfolioCompany:
        created_at = datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO portfolio_companies (
                    company_name,
                    website,
                    sector,
                    country,
                    thesis,
                    notes,
                    keywords_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company.company_name,
                    company.website,
                    company.sector,
                    company.country,
                    company.thesis,
                    company.notes,
                    json.dumps(company.keywords),
                    created_at.isoformat(),
                ),
            )
            connection.commit()
            company_id = int(cursor.lastrowid)

        return PortfolioCompany(
            id=company_id,
            created_at=created_at,
            **company.model_dump(),
        )

    def list_companies(self) -> list[PortfolioCompany]:
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT id, company_name, website, sector, country, thesis, notes, keywords_json, created_at
                FROM portfolio_companies
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()

        companies: list[PortfolioCompany] = []
        for row in rows:
            companies.append(
                PortfolioCompany(
                    id=int(row["id"]),
                    company_name=row["company_name"],
                    website=row["website"],
                    sector=row["sector"],
                    country=row["country"],
                    thesis=row["thesis"],
                    notes=row["notes"],
                    keywords=json.loads(row["keywords_json"] or "[]"),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )
        return companies
