from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

import httpx

from app.models import EvidenceItem, ResearchMetrics
from app.utils.text import build_keyword_query


logger = logging.getLogger(__name__)


class OpenAlexClient:
    base_url = "https://api.openalex.org/works"

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.http_client = http_client

    async def fetch_research(self, sector: str, description: str) -> ResearchMetrics:
        query = build_keyword_query([sector, description], max_terms=8)
        if not query:
            return ResearchMetrics(limitations=["OpenAlex query could not be built from the input."])

        params = {
            "search": query,
            "per-page": 10,
            "sort": "publication_year:desc",
        }

        try:
            response = await self.http_client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            logger.warning("OpenAlex lookup failed: %s", exc)
            return ResearchMetrics(limitations=[f"OpenAlex lookup failed: {exc}"])

        works = payload.get("results") or []
        if not works:
            return ResearchMetrics(
                limitations=["OpenAlex returned no directly relevant works for the query."],
                provider_confidence=0.3,
            )

        current_year = datetime.now(timezone.utc).year
        publication_years: list[int] = []
        top_titles: list[str] = []
        topic_counter: Counter[str] = Counter()
        evidence: list[EvidenceItem] = []

        for work in works[:10]:
            title = (work.get("display_name") or "").strip()
            if title:
                top_titles.append(title)
            publication_year = work.get("publication_year")
            if isinstance(publication_year, int):
                publication_years.append(publication_year)
            for concept in work.get("concepts") or []:
                concept_name = concept.get("display_name")
                if concept_name:
                    topic_counter.update([concept_name])

            if title:
                finding = f"{publication_year or 'n.d.'}: {title}"
                evidence.append(
                    EvidenceItem(
                        source="openalex",
                        finding=finding,
                        url=work.get("id") or self.base_url,
                    )
                )

        recent_paper_count = sum(1 for year in publication_years if year >= current_year - 2)
        prior_paper_count = sum(1 for year in publication_years if current_year - 5 <= year < current_year - 2)
        trend_ratio = (recent_paper_count - prior_paper_count) / max(prior_paper_count, 1)

        return ResearchMetrics(
            recent_paper_count=recent_paper_count,
            publication_years=publication_years,
            top_titles=top_titles[:5],
            topics=[topic for topic, _ in topic_counter.most_common(8)],
            trend_ratio=trend_ratio,
            latest_publication_year=max(publication_years) if publication_years else None,
            evidence=evidence[:5],
            provider_confidence=0.85,
        )
