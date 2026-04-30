from io import BytesIO

from fastapi.testclient import TestClient
from pptx import Presentation

from app.main import app
from app.models import CompetitorMetrics, DocumentContent, PatentMetrics, ResearchMetrics, StartupSignals, WebsiteContent
from app.scoring import CURRENT_YEAR
from app.services.llm_extractor import LLMExtractor
from app.services.openalex_client import OpenAlexClient
from app.services.patents_provider import PlaceholderPatentsProvider
from app.services.search_provider import PlaceholderSearchProvider
from app.services.website_fetcher import WebsiteFetcher


def test_score_startup_accepts_multipart_with_optional_document(monkeypatch) -> None:
    async def fake_fetch_website(self, website: str) -> WebsiteContent:
        return WebsiteContent(
            url=website,
            title="Example AI",
            meta_description="AI platform for hospitals",
            text="Hospital automation workflow platform",
            fetched=True,
        )

    async def fake_fetch_research(self, sector: str, description: str) -> ResearchMetrics:
        return ResearchMetrics(
            recent_paper_count=3,
            publication_years=[CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2],
            top_titles=["Hospital Workflow AI"],
            topics=["Health AI", "Clinical operations"],
            trend_ratio=0.5,
            latest_publication_year=CURRENT_YEAR,
            provider_confidence=0.8,
        )

    async def fake_search_patents(self, startup) -> PatentMetrics:
        return PatentMetrics(provider_confidence=0.0)

    async def fake_search_competitors(self, startup) -> CompetitorMetrics:
        return CompetitorMetrics(provider_confidence=0.0)

    async def fake_extract_signals(self, startup, website, document, research, patents, competitors):
        return (
            StartupSignals(
                product_category="HealthTech AI",
                target_customer="Hospitals",
                claimed_innovation="AI workflow automation for hospital operations",
                technical_keywords=["hospital", "automation", "workflow"],
                market_trends=["Operational efficiency", "Clinical AI"],
                evidence_summary=["Pitch deck and website both describe hospital workflow automation."],
                website_signal_present=True,
            ),
            [],
        )

    monkeypatch.setattr(WebsiteFetcher, "fetch", fake_fetch_website)
    monkeypatch.setattr(OpenAlexClient, "fetch_research", fake_fetch_research)
    monkeypatch.setattr(PlaceholderPatentsProvider, "search", fake_search_patents)
    monkeypatch.setattr(PlaceholderSearchProvider, "search", fake_search_competitors)
    monkeypatch.setattr(LLMExtractor, "extract_signals", fake_extract_signals)

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Example AI"
    slide.placeholders[1].text = "AI platform for hospital workflow automation"
    buffer = BytesIO()
    presentation.save(buffer)
    buffer.seek(0)

    with TestClient(app) as client:
        response = client.post(
            "/score-startup",
            data={
                "website": "https://example.com",
                "sector": "HealthTech AI",
                "meeting_notes": "Founder emphasized workflow automation and hospital deployment plans.",
            },
            files={
                "supporting_document": (
                    "deck.pptx",
                    buffer.getvalue(),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["startup_name"] == "Example"
    assert payload["novelty_score"] >= 0
    assert any(item["source"] == "document_pptx" for item in payload["evidence"])
    assert any(item["source"] == "meeting_notes" for item in payload["evidence"])
