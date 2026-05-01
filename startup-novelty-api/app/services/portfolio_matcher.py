from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlparse

from app.models import (
    DocumentContent,
    PortfolioCheckResult,
    PortfolioCompany,
    PortfolioMatch,
    StartupScoreRequest,
    WebsiteContent,
)
from app.utils.text import extract_keywords, normalize_whitespace, truncate_text


@dataclass
class MatchSignals:
    overlap_score: int
    match_type: str
    shared_keywords: list[str]
    rationale: str


class PortfolioMatcher:
    def check_overlap(
        self,
        startup: StartupScoreRequest,
        website: WebsiteContent,
        document: DocumentContent,
        portfolio_companies: list[PortfolioCompany],
    ) -> PortfolioCheckResult:
        if not portfolio_companies:
            return PortfolioCheckResult(checked=True, portfolio_company_count=0)

        startup_domain = self._domain_from_url(startup.website)
        startup_text = normalize_whitespace(
            " ".join(
                part
                for part in [
                    startup.startup_name,
                    startup.description,
                    startup.sector,
                    startup.meeting_notes,
                    website.title,
                    website.meta_description,
                    truncate_text(website.text, 1800),
                    truncate_text(document.text, 1800),
                ]
                if part
            )
        )
        startup_keywords = set(extract_keywords(startup_text, max_keywords=18))
        startup_sector_keywords = set(extract_keywords(startup.sector, max_keywords=6))
        matches: list[PortfolioMatch] = []

        for company in portfolio_companies:
            signals = self._score_company(
                startup=startup,
                startup_domain=startup_domain,
                startup_keywords=startup_keywords,
                startup_sector_keywords=startup_sector_keywords,
                company=company,
            )
            if signals is None:
                continue
            matches.append(
                PortfolioMatch(
                    company_id=company.id,
                    company_name=company.company_name,
                    website=company.website,
                    sector=company.sector,
                    overlap_score=signals.overlap_score,
                    match_type=signals.match_type,  # type: ignore[arg-type]
                    shared_keywords=signals.shared_keywords,
                    rationale=signals.rationale,
                )
            )

        matches.sort(key=lambda item: item.overlap_score, reverse=True)
        top_matches = matches[:5]
        top_score = top_matches[0].overlap_score if top_matches else 0
        overlap_level = "none"
        if top_score >= 95:
            overlap_level = "exact"
        elif top_score >= 75:
            overlap_level = "strong"
        elif top_score >= 50:
            overlap_level = "related"

        return PortfolioCheckResult(
            checked=True,
            portfolio_company_count=len(portfolio_companies),
            overlap_score=top_score,
            overlap_level=overlap_level,  # type: ignore[arg-type]
            has_similar_investment=top_score >= 50,
            top_matches=top_matches,
        )

    def _score_company(
        self,
        startup: StartupScoreRequest,
        startup_domain: str,
        startup_keywords: set[str],
        startup_sector_keywords: set[str],
        company: PortfolioCompany,
    ) -> MatchSignals | None:
        company_domain = self._domain_from_url(company.website or "")
        exact_domain_match = bool(startup_domain and company_domain and startup_domain == company_domain)
        name_similarity = SequenceMatcher(
            None,
            startup.startup_name.lower(),
            company.company_name.lower(),
        ).ratio()

        company_keywords = {keyword.strip().lower() for keyword in company.keywords if keyword.strip()} | set(
            extract_keywords(" ".join([company.sector, company.thesis, company.notes]), max_keywords=16)
        )
        shared_keywords = sorted(startup_keywords & company_keywords)[:8]
        if company_keywords and startup_keywords:
            startup_coverage = len(shared_keywords) / max(len(startup_keywords), 1)
            company_coverage = len(shared_keywords) / max(len(company_keywords), 1)
            keyword_similarity = (startup_coverage * 0.65) + (company_coverage * 0.35)
        else:
            keyword_similarity = 0.0
        company_sector_keywords = set(extract_keywords(company.sector, max_keywords=6))
        sector_similarity = (
            len(startup_sector_keywords & company_sector_keywords) / max(len(startup_sector_keywords | company_sector_keywords), 1)
            if startup_sector_keywords and company_sector_keywords
            else 0.0
        )

        if exact_domain_match:
            return MatchSignals(
                overlap_score=100,
                match_type="exact",
                shared_keywords=shared_keywords,
                rationale="Exact website/domain match with an existing portfolio company.",
            )

        overlap_score = round((keyword_similarity * 60) + (sector_similarity * 25) + (name_similarity * 15))
        if overlap_score < 35:
            return None

        if overlap_score >= 75:
            match_type = "strong"
        else:
            match_type = "related"

        rationale_parts = []
        if shared_keywords:
            rationale_parts.append(f"Shared keywords: {', '.join(shared_keywords[:5])}.")
        if sector_similarity >= 0.5:
            rationale_parts.append("Sector overlap is high.")
        if name_similarity >= 0.6:
            rationale_parts.append("Company naming is unusually similar.")
        if not rationale_parts:
            rationale_parts.append("The thesis and category overlap with an existing investment.")

        return MatchSignals(
            overlap_score=min(overlap_score, 99),
            match_type=match_type,
            shared_keywords=shared_keywords,
            rationale=" ".join(rationale_parts),
        )

    @staticmethod
    def _domain_from_url(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower().removeprefix("www.")
