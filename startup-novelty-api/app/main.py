from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.models import (
    CompetitorMetrics,
    CRMCompany,
    CRMCompanyCreate,
    CRMRecordResult,
    CRMPitch,
    CRMPitchCreate,
    CRMSummaryResponse,
    DocumentContent,
    EvidenceItem,
    PatentMetrics,
    PortfolioCheckResult,
    PortfolioCompany,
    PortfolioCompanyCreate,
    ResearchMetrics,
    StartupAnalysisResponse,
    StartupScoreRequest,
    StartupSignals,
    WebsiteContent,
)
from app.scoring import calculate_scores
from app.services.crm_repository import CRMRepository
from app.services.document_parser import DocumentParser
from app.services.llm_extractor import LLMExtractor
from app.services.openalex_client import OpenAlexClient
from app.services.openrouter_client import OpenRouterClient
from app.services.patents_provider import PlaceholderPatentsProvider
from app.services.portfolio_matcher import PortfolioMatcher
from app.services.portfolio_repository import PortfolioRepository
from app.services.search_provider import PlaceholderSearchProvider
from app.services.website_fetcher import WebsiteFetcher
from app.utils.text import extract_keywords, truncate_text


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
    portfolio_repository = PortfolioRepository(Path(settings.vc_portfolio_db_path))
    crm_repository = CRMRepository(Path(settings.vc_portfolio_db_path))
    portfolio_repository.init_db()
    crm_repository.init_db()
    app.state.settings = settings
    app.state.http_client = httpx.AsyncClient(timeout=timeout)
    app.state.portfolio_repository = portfolio_repository
    app.state.crm_repository = crm_repository
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
    portfolio_check: PortfolioCheckResult,
    website: WebsiteContent,
    document: DocumentContent,
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
    innovation = signals.claimed_innovation or startup.description or truncate_text(document.text, 220)
    portfolio_phrase = ""
    if portfolio_check.overlap_level == "exact":
        portfolio_phrase = " An exact match was found in the VC portfolio database."
    elif portfolio_check.overlap_level == "strong":
        portfolio_phrase = " The startup strongly overlaps with an existing portfolio investment."
    elif portfolio_check.overlap_level == "related":
        portfolio_phrase = " The startup appears related to an existing portfolio investment."
    website_phrase = "Website messaging was incorporated." if website.fetched else "Website evidence was unavailable."
    document_phrase = (
        f" Uploaded {document.document_type.upper()} materials were incorporated."
        if document.extracted
        else ""
    )
    meeting_phrase = " Meeting transcript notes were incorporated." if startup.meeting_notes else ""
    limitation_phrase = (
        " Placeholder data providers reduced certainty."
        if limitations
        else ""
    )
    return (
        f"{startup.startup_name} shows {novelty_phrase} novelty signals in {startup.sector}. "
        f"Claimed innovation centers on {innovation}. "
        f"The current evidence suggests {market_phrase}, and {research_phrase}. "
        f"{website_phrase}{document_phrase}{meeting_phrase}{portfolio_phrase}{limitation_phrase}"
    )


def _aggregate_evidence(
    startup: StartupScoreRequest,
    website: WebsiteContent,
    document: DocumentContent,
    portfolio_check: PortfolioCheckResult,
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

    if document.extracted:
        evidence.append(
            EvidenceItem(
                source=f"document_{document.document_type}",
                finding=truncate_text(document.text, 240),
                url=document.filename,
            )
        )

    if startup.meeting_notes:
        evidence.append(
            EvidenceItem(
                source="meeting_notes",
                finding=truncate_text(startup.meeting_notes, 240),
                url=None,
            )
        )

    for match in portfolio_check.top_matches[:3]:
        evidence.append(
            EvidenceItem(
                source="portfolio_database",
                finding=f"{match.company_name}: {match.rationale}",
                url=match.website,
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


def _derive_startup_name(
    website: str | None,
    startup_name: str | None,
    document_filename: str | None = None,
) -> str:
    if startup_name and startup_name.strip():
        return startup_name.strip()

    if website:
        hostname = urlparse(website).netloc.lower().removeprefix("www.")
        base_name = hostname.split(".")[0] if hostname else ""
        if base_name:
            return " ".join(part.capitalize() for part in base_name.replace("_", "-").split("-"))

    if document_filename:
        base_name = Path(document_filename).stem
        cleaned = " ".join(part.capitalize() for part in base_name.replace("_", "-").split("-") if part)
        if cleaned:
            return cleaned

    return "Uploaded Startup"


def _build_research_query_description(
    startup: StartupScoreRequest,
    website: WebsiteContent,
    document: DocumentContent,
) -> str:
    combined = " ".join(
        part
        for part in [
            startup.description,
            startup.meeting_notes,
            website.title,
            website.meta_description,
            truncate_text(website.text, 1_200),
            truncate_text(document.text, 1_200),
        ]
        if part
    )
    return truncate_text(combined, 2_500)


def _parse_csv_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.split(",") if part.strip()]


def _parse_pitch_date(raw_value: str | None) -> date:
    if not raw_value:
        return datetime.now(timezone.utc).date()
    return date.fromisoformat(raw_value)


def _build_crm_company_payload(
    startup: StartupScoreRequest,
    founder_names: list[str],
    contact_email: str | None,
    crm_notes: str,
) -> CRMCompanyCreate:
    keywords = extract_keywords(" ".join([startup.sector, startup.description, startup.meeting_notes]), max_keywords=12)
    return CRMCompanyCreate(
        company_name=startup.startup_name,
        website=startup.website,
        sector=startup.sector,
        country=startup.country,
        description=startup.description,
        founder_names=founder_names,
        contact_email=contact_email,
        notes=crm_notes,
        keywords=keywords,
    )


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    portfolio_repository: PortfolioRepository = request.app.state.portfolio_repository
    crm_repository: CRMRepository = request.app.state.crm_repository
    company_count = await asyncio.to_thread(lambda: len(portfolio_repository.list_companies()))
    crm_company_count = await asyncio.to_thread(lambda: len(crm_repository.list_companies()))
    crm_pitch_count = await asyncio.to_thread(lambda: len(crm_repository.list_pitches()))
    return {
        "status": "ok",
        "environment": settings.app_env,
        "model": settings.openrouter_model,
        "portfolio_company_count": str(company_count),
        "crm_company_count": str(crm_company_count),
        "crm_pitch_count": str(crm_pitch_count),
    }


@app.get("/portfolio-companies", response_model=list[PortfolioCompany])
async def list_portfolio_companies(request: Request) -> list[PortfolioCompany]:
    portfolio_repository: PortfolioRepository = request.app.state.portfolio_repository
    return await asyncio.to_thread(portfolio_repository.list_companies)


@app.post("/portfolio-companies", response_model=PortfolioCompany)
async def create_portfolio_company(
    request: Request,
    payload: PortfolioCompanyCreate,
) -> PortfolioCompany:
    portfolio_repository: PortfolioRepository = request.app.state.portfolio_repository
    return await asyncio.to_thread(portfolio_repository.add_company, payload)


@app.get("/crm/companies", response_model=list[CRMCompany])
async def list_crm_companies(request: Request) -> list[CRMCompany]:
    crm_repository: CRMRepository = request.app.state.crm_repository
    return await asyncio.to_thread(crm_repository.list_companies)


@app.post("/crm/companies", response_model=CRMCompany)
async def upsert_crm_company(request: Request, payload: CRMCompanyCreate) -> CRMCompany:
    crm_repository: CRMRepository = request.app.state.crm_repository
    return await asyncio.to_thread(crm_repository.upsert_company, payload)


@app.get("/crm/pitches", response_model=list[CRMPitch])
async def list_crm_pitches(request: Request) -> list[CRMPitch]:
    crm_repository: CRMRepository = request.app.state.crm_repository
    return await asyncio.to_thread(crm_repository.list_pitches)


@app.post("/crm/pitches", response_model=CRMPitch)
async def create_crm_pitch(request: Request, payload: CRMPitchCreate) -> CRMPitch:
    crm_repository: CRMRepository = request.app.state.crm_repository
    return await asyncio.to_thread(crm_repository.create_pitch, payload)


@app.get("/crm/summary", response_model=CRMSummaryResponse)
async def crm_summary(request: Request) -> CRMSummaryResponse:
    crm_repository: CRMRepository = request.app.state.crm_repository
    return await asyncio.to_thread(crm_repository.get_summary)


@app.post("/score-startup", response_model=StartupAnalysisResponse)
async def score_startup(
    request: Request,
    website: str | None = Form(default=None),
    startup_name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    sector: str | None = Form(default=None),
    country: str | None = Form(default=None),
    meeting_notes: str | None = Form(default=None),
    founder_names: str | None = Form(default=None),
    contact_email: str | None = Form(default=None),
    pitch_date: str | None = Form(default=None),
    deal_status: str = Form(default="new"),
    funding_status: str = Form(default="unknown"),
    round_name: str | None = Form(default=None),
    amount_requested_usd: float | None = Form(default=None),
    crm_notes: str | None = Form(default=None),
    crm_source: str | None = Form(default="frontend_upload"),
    record_in_crm: bool = Form(default=True),
    supporting_document: UploadFile = File(...),
) -> StartupAnalysisResponse:
    settings: Settings = request.app.state.settings
    http_client: httpx.AsyncClient = request.app.state.http_client
    payload = StartupScoreRequest(
        startup_name=_derive_startup_name(website, startup_name),
        website=website or "",
        description=description or "",
        sector=sector or "Unknown Sector",
        country=country or "Unknown",
        meeting_notes=meeting_notes or "",
    )

    website_fetcher = WebsiteFetcher(http_client)
    document_parser = DocumentParser()
    openalex_client = OpenAlexClient(http_client)
    patents_provider = PlaceholderPatentsProvider()
    portfolio_matcher = PortfolioMatcher()
    portfolio_repository: PortfolioRepository = request.app.state.portfolio_repository
    crm_repository: CRMRepository = request.app.state.crm_repository
    search_provider = PlaceholderSearchProvider()
    llm_extractor = LLMExtractor(OpenRouterClient(http_client, settings))

    website_result: WebsiteContent
    document_result: DocumentContent
    crm_record = CRMRecordResult()
    portfolio_check: PortfolioCheckResult
    research_result: ResearchMetrics
    patent_result: PatentMetrics
    competitor_result: CompetitorMetrics
    limitations: list[str] = []

    results = await asyncio.gather(
        website_fetcher.fetch(payload.website),
        document_parser.parse(supporting_document),
        asyncio.to_thread(portfolio_repository.list_companies),
        patents_provider.search(payload),
        search_provider.search(payload),
        return_exceptions=True,
    )

    website_result = WebsiteContent()
    document_result = DocumentContent()
    portfolio_check = PortfolioCheckResult()
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
            document_result = result
        elif index == 2:
            portfolio_check = portfolio_matcher.check_overlap(payload, website_result, document_result, result)
        elif index == 3:
            patent_result = result
        elif index == 4:
            competitor_result = result

    if not startup_name and not payload.website:
        payload.startup_name = _derive_startup_name(payload.website, startup_name, document_result.filename)

    limitations.extend(website_result.limitations)
    limitations.extend(document_result.limitations)
    limitations.extend(patent_result.limitations)
    limitations.extend(competitor_result.limitations)

    if record_in_crm:
        try:
            saved_company, saved_pitch = await asyncio.to_thread(
                crm_repository.record_pitch_for_company,
                _build_crm_company_payload(
                    startup=payload,
                    founder_names=_parse_csv_list(founder_names),
                    contact_email=contact_email.strip() if contact_email else None,
                    crm_notes=(crm_notes or "").strip(),
                ),
                CRMPitchCreate(
                    company_id=1,
                    pitch_date=_parse_pitch_date(pitch_date),
                    deal_status=deal_status,  # type: ignore[arg-type]
                    funding_status=funding_status,  # type: ignore[arg-type]
                    round_name=(round_name or "").strip(),
                    amount_requested_usd=amount_requested_usd,
                    source=(crm_source or "frontend_upload").strip(),
                    notes=(crm_notes or "").strip(),
                ),
            )
            crm_record = CRMRecordResult(recorded=True, company_id=saved_company.id, pitch_id=saved_pitch.id)
        except Exception as exc:
            logger.error("CRM recording failed: %s", exc)
            limitations.append(f"CRM recording failed: {exc}")

    research_query_description = _build_research_query_description(payload, website_result, document_result)
    research_result = await openalex_client.fetch_research(payload.sector, research_query_description)
    limitations.extend(research_result.limitations)

    signals, llm_limitations = await llm_extractor.extract_signals(
        startup=payload,
        website=website_result,
        document=document_result,
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
        document=document_result,
        portfolio_check=portfolio_check,
        research=research_result,
        patents=patent_result,
        competitors=competitor_result,
        signals=signals,
    )

    response = StartupAnalysisResponse(
        startup_name=payload.startup_name,
        summary=_build_summary(
            payload,
            signals,
            research_result,
            None,
            portfolio_check,
            website_result,
            document_result,
            limitations,
        ),
        portfolio_check=portfolio_check,
        crm_record=crm_record,
        evidence=evidence,
        limitations=sorted(set(limitations)),
        **scores.model_dump(),
    )
    response.summary = _build_summary(
        payload,
        signals,
        research_result,
        response,
        portfolio_check,
        website_result,
        document_result,
        response.limitations,
    )
    return response
