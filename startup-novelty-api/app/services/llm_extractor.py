from __future__ import annotations

import json
import logging

from app.models import (
    CompetitorMetrics,
    DocumentContent,
    LLMExtractedSignals,
    PatentMetrics,
    ResearchMetrics,
    StartupScoreRequest,
    StartupSignals,
    WebsiteContent,
)
from app.services.openrouter_client import OpenRouterClient
from app.utils.errors import ExternalServiceError
from app.utils.text import build_keyword_query, extract_json_object, extract_keywords, truncate_text


logger = logging.getLogger(__name__)


class LLMExtractor:
    def __init__(self, client: OpenRouterClient) -> None:
        self.client = client

    async def extract_signals(
        self,
        startup: StartupScoreRequest,
        website: WebsiteContent,
        document: DocumentContent,
        research: ResearchMetrics,
        patents: PatentMetrics,
        competitors: CompetitorMetrics,
    ) -> tuple[StartupSignals, list[str]]:
        messages = self._build_messages(startup, website, document, research, patents, competitors)
        limitations: list[str] = []

        try:
            raw_content = await self.client.chat_completion(messages)
            extracted = self._parse_llm_json(raw_content)
            return self._to_startup_signals(extracted, website), limitations
        except (ExternalServiceError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("LLM extraction failed, using fallback signals: %s", exc)
            limitations.append(f"LLM extraction fallback was used: {exc}")
            return self._fallback_signals(startup, website, document, research, competitors), limitations

    def _build_messages(
        self,
        startup: StartupScoreRequest,
        website: WebsiteContent,
        document: DocumentContent,
        research: ResearchMetrics,
        patents: PatentMetrics,
        competitors: CompetitorMetrics,
    ) -> list[dict[str, str]]:
        research_summary = {
            "recent_paper_count": research.recent_paper_count,
            "publication_years": research.publication_years[:10],
            "top_titles": research.top_titles,
            "topics": research.topics,
        }
        patent_summary = {
            "similar_patent_count": patents.similar_patent_count,
            "close_match_count": patents.close_match_count,
            "limitations": patents.limitations,
        }
        competitor_summary = {
            "competitor_count": competitors.competitor_count,
            "close_competitor_count": competitors.close_competitor_count,
            "named_competitors": competitors.named_competitors,
            "limitations": competitors.limitations,
        }

        content = {
            "startup_name": startup.startup_name,
            "website": startup.website,
            "description": startup.description,
            "sector": startup.sector,
            "country": startup.country,
            "meeting_notes_excerpt": truncate_text(startup.meeting_notes, 4_000),
            "website_title": website.title,
            "website_meta_description": website.meta_description,
            "website_text_excerpt": truncate_text(website.text, 4_500),
            "document_filename": document.filename,
            "document_type": document.document_type,
            "document_text_excerpt": truncate_text(document.text, 4_500),
            "research_summary": research_summary,
            "patent_summary": patent_summary,
            "competitor_summary": competitor_summary,
        }

        schema = {
            "product_category": "string",
            "target_customer": "string",
            "claimed_innovation": "string",
            "competitors": ["string"],
            "market_trends": ["string"],
            "technical_keywords": ["string"],
            "risks": ["string"],
            "evidence_summary": ["string"],
        }

        return [
            {
                "role": "system",
                "content": (
                    "You extract VC due-diligence signals. Return valid JSON only. "
                    "Do not add markdown, comments, or prose outside the JSON object."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Extract structured signals from this startup context.\n"
                    f"Required JSON schema: {json.dumps(schema)}\n"
                    f"Context: {json.dumps(content)}"
                ),
            },
        ]

    def _parse_llm_json(self, raw_content: str) -> LLMExtractedSignals:
        parsed = extract_json_object(raw_content)
        return LLMExtractedSignals.model_validate(parsed)

    def _to_startup_signals(
        self,
        extracted: LLMExtractedSignals,
        website: WebsiteContent,
    ) -> StartupSignals:
        return StartupSignals(
            product_category=extracted.product_category,
            target_customer=extracted.target_customer,
            claimed_innovation=extracted.claimed_innovation,
            competitors=extracted.competitors,
            market_trends=extracted.market_trends,
            technical_keywords=extracted.technical_keywords,
            risks=extracted.risks,
            evidence_summary=extracted.evidence_summary,
            website_signal_present=website.fetched and bool(website.text),
        )

    def _fallback_signals(
        self,
        startup: StartupScoreRequest,
        website: WebsiteContent,
        document: DocumentContent,
        research: ResearchMetrics,
        competitors: CompetitorMetrics,
    ) -> StartupSignals:
        technical_keywords = extract_keywords(
            " ".join(
                [
                    startup.sector,
                    startup.description,
                    startup.meeting_notes,
                    website.title,
                    website.meta_description,
                    document.text,
                    " ".join(research.topics),
                ]
            ),
            max_keywords=10,
        )
        market_trends = research.topics[:4]
        competitor_names = competitors.named_competitors[:5]
        fallback_risks = list(competitors.limitations[:1])
        if not website.fetched:
            fallback_risks.append("Website evidence was limited or unavailable.")
        if research.recent_paper_count == 0:
            fallback_risks.append("Limited recent public research evidence was found.")

        return StartupSignals(
            product_category=startup.sector,
            target_customer="",
            claimed_innovation=startup.description,
            competitors=competitor_names,
            market_trends=market_trends,
            technical_keywords=technical_keywords or build_keyword_query([startup.sector, startup.description]).split(),
            risks=fallback_risks[:5],
            evidence_summary=[
                summary
                for summary in [
                    website.meta_description or website.title,
                    truncate_text(document.text, 220) if document.extracted else "",
                    truncate_text(startup.meeting_notes, 220) if startup.meeting_notes else "",
                    research.top_titles[0] if research.top_titles else "",
                ]
                if summary
            ],
            website_signal_present=website.fetched and bool(website.text),
        )
