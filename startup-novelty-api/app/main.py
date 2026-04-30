from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.models import (
    CompetitorMetrics,
    EvidenceItem,
    PatentMetrics,
    ResearchMetrics,
    StartupAnalysisResponse,
    StartupScoreRequest,
    StartupSignals,
    WebsiteContent,
)
from app.scoring import calculate_scores
from app.services.llm_extractor import LLMExtractor
from app.services.openalex_client import OpenAlexClient
from app.services.openrouter_client import OpenRouterClient
from app.services.patents_provider import PlaceholderPatentsProvider
from app.services.search_provider import PlaceholderSearchProvider
from app.services.website_fetcher import WebsiteFetcher


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    timeout = httpx.Timeout(settings.http_timeout_seconds)
    app.state.settings = settings
    app.state.http_client = httpx.AsyncClient(timeout=timeout)
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="Startup Novelty API",
    description="Novelty and long-term investability signal scoring for VC due diligence.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)


def _build_summary(
    startup: StartupScoreRequest,
    signals: StartupSignals,
    research: ResearchMetrics,
    scores: StartupAnalysisResponse | None,
    website: WebsiteContent,
    limitations: list[str],
) -> str:
    novelty_phrase = (
        "strong" if scores and scores.novelty_score >= 75 else "moderate" if scores and scores.novelty_score >= 55 else "limited"
    )
    market_phrase = (
        "positive market timing indicators"
        if scores and scores.market_score >= 60
        else "mixed market timing indicators"
    )
    research_phrase = (
        f"{research.recent_paper_count} recent sector-adjacent research items were found"
        if research.recent_paper_count
        else "public research evidence is currently limited"
    )
    innovation = signals.claimed_innovation or startup.description
    website_phrase = "Website messaging was incorporated." if website.fetched else "Website evidence was unavailable."
    limitation_phrase = (
        " Placeholder data providers reduced certainty."
        if limitations
        else ""
    )
    return (
        f"{startup.startup_name} shows {novelty_phrase} novelty signals in {startup.sector}. "
        f"Claimed innovation centers on {innovation}. "
        f"The current evidence suggests {market_phrase}, and {research_phrase}. "
        f"{website_phrase}{limitation_phrase}"
    )


def _aggregate_evidence(
    startup: StartupScoreRequest,
    website: WebsiteContent,
    research: ResearchMetrics,
    patents: PatentMetrics,
    competitors: CompetitorMetrics,
    signals: StartupSignals,
) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []

    if website.fetched and (website.meta_description or startup.description):
        evidence.append(
            EvidenceItem(
                source="website",
                finding=website.meta_description or startup.description,
                url=website.url or startup.website,
            )
        )
    elif startup.description:
        evidence.append(
            EvidenceItem(
                source="startup_input",
                finding=startup.description,
                url=startup.website,
            )
        )

    evidence.extend(research.evidence[:4])
    evidence.extend(patents.evidence[:2])
    evidence.extend(competitors.evidence[:2])

    for summary in signals.evidence_summary[:2]:
        evidence.append(EvidenceItem(source="llm_extraction", finding=summary, url=startup.website))

    deduped: list[EvidenceItem] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in evidence:
        key = (item.source, item.finding, item.url)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:10]


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    return {
        "status": "ok",
        "environment": settings.app_env,
        "model": settings.openrouter_model,
    }


@app.post("/score-startup", response_model=StartupAnalysisResponse)
async def score_startup(payload: StartupScoreRequest, request: Request) -> StartupAnalysisResponse:
    settings: Settings = request.app.state.settings
    http_client: httpx.AsyncClient = request.app.state.http_client

    website_fetcher = WebsiteFetcher(http_client)
    openalex_client = OpenAlexClient(http_client)
    patents_provider = PlaceholderPatentsProvider()
    search_provider = PlaceholderSearchProvider()
    llm_extractor = LLMExtractor(OpenRouterClient(http_client, settings))

    website_result: WebsiteContent
    research_result: ResearchMetrics
    patent_result: PatentMetrics
    competitor_result: CompetitorMetrics
    limitations: list[str] = []

    results = await asyncio.gather(
        website_fetcher.fetch(payload.website),
        openalex_client.fetch_research(payload.sector, payload.description),
        patents_provider.search(payload),
        search_provider.search(payload),
        return_exceptions=True,
    )

    website_result = WebsiteContent()
    research_result = ResearchMetrics()
    patent_result = PatentMetrics()
    competitor_result = CompetitorMetrics()

    for index, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("Data source task %s failed: %s", index, result)
            limitations.append(f"Data source {index} failed: {result}")
            continue
        if index == 0:
            website_result = result
        elif index == 1:
            research_result = result
        elif index == 2:
            patent_result = result
        elif index == 3:
            competitor_result = result

    limitations.extend(website_result.limitations)
    limitations.extend(research_result.limitations)
    limitations.extend(patent_result.limitations)
    limitations.extend(competitor_result.limitations)

    signals, llm_limitations = await llm_extractor.extract_signals(
        startup=payload,
        website=website_result,
        research=research_result,
        patents=patent_result,
        competitors=competitor_result,
    )
    limitations.extend(llm_limitations)

    scores = calculate_scores(
        signals=signals,
        research_metrics=research_result,
        patent_metrics=patent_result,
        competitor_metrics=competitor_result,
    )

    evidence = _aggregate_evidence(
        startup=payload,
        website=website_result,
        research=research_result,
        patents=patent_result,
        competitors=competitor_result,
        signals=signals,
    )

    response = StartupAnalysisResponse(
        startup_name=payload.startup_name,
        summary=_build_summary(payload, signals, research_result, None, website_result, limitations),
        evidence=evidence,
        limitations=sorted(set(limitations)),
        **scores.model_dump(),
    )
    response.summary = _build_summary(payload, signals, research_result, response, website_result, response.limitations)
    return response
