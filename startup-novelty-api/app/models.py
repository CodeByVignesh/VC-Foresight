from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StartupScoreRequest(BaseModel):
    startup_name: str = Field(min_length=1, max_length=200)
    website: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=4_000)
    sector: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=100)
    meeting_notes: str = Field(default="", max_length=20_000)

    @field_validator("startup_name", "website", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", "sector", "country", "meeting_notes", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str:
        return value.strip() if value else ""


class EvidenceItem(BaseModel):
    source: str
    finding: str
    url: str | None = None


class WebsiteContent(BaseModel):
    url: str | None = None
    title: str = ""
    meta_description: str = ""
    text: str = ""
    fetched: bool = False
    limitations: list[str] = Field(default_factory=list)


class DocumentContent(BaseModel):
    filename: str = ""
    document_type: str = ""
    text: str = ""
    extracted: bool = False
    limitations: list[str] = Field(default_factory=list)


class ResearchMetrics(BaseModel):
    recent_paper_count: int = 0
    publication_years: list[int] = Field(default_factory=list)
    top_titles: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    trend_ratio: float = 0.0
    latest_publication_year: int | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provider_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PatentMetrics(BaseModel):
    similar_patent_count: int = 0
    close_match_count: int = 0
    distinct_cpc_codes: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provider_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CompetitorMetrics(BaseModel):
    competitor_count: int = 0
    close_competitor_count: int = 0
    named_competitors: list[str] = Field(default_factory=list)
    whitespace_score_hint: int = Field(default=50, ge=0, le=100)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provider_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LLMExtractedSignals(BaseModel):
    product_category: str = ""
    target_customer: str = ""
    claimed_innovation: str = ""
    competitors: list[str] = Field(default_factory=list)
    market_trends: list[str] = Field(default_factory=list)
    technical_keywords: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)


class StartupSignals(BaseModel):
    product_category: str = ""
    target_customer: str = ""
    claimed_innovation: str = ""
    competitors: list[str] = Field(default_factory=list)
    market_trends: list[str] = Field(default_factory=list)
    technical_keywords: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    website_signal_present: bool = False


class PortfolioCompanyCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    sector: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=100)
    thesis: str = Field(default="", max_length=6_000)
    notes: str = Field(default="", max_length=6_000)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("company_name", mode="before")
    @classmethod
    def strip_company_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("website", mode="before")
    @classmethod
    def strip_company_website(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("sector", "country", "thesis", "notes", mode="before")
    @classmethod
    def strip_company_text(cls, value: str | None) -> str:
        return value.strip() if value else ""


class PortfolioCompany(PortfolioCompanyCreate):
    id: int
    created_at: datetime


class PortfolioMatch(BaseModel):
    company_id: int
    company_name: str
    website: str | None = None
    sector: str = ""
    overlap_score: int = Field(ge=0, le=100)
    match_type: Literal["exact", "strong", "related"]
    shared_keywords: list[str] = Field(default_factory=list)
    rationale: str


class PortfolioCheckResult(BaseModel):
    checked: bool = False
    portfolio_company_count: int = 0
    overlap_score: int = Field(default=0, ge=0, le=100)
    overlap_level: Literal["none", "related", "strong", "exact"] = "none"
    has_similar_investment: bool = False
    top_matches: list[PortfolioMatch] = Field(default_factory=list)


DealStatus = Literal["new", "screening", "partner_review", "due_diligence", "passed", "invested"]
FundingStatus = Literal[
    "unknown",
    "seeking",
    "not_raising",
    "in_discussion",
    "due_diligence",
    "term_sheet",
    "invested",
    "passed",
]


class CRMCompanyCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    sector: str = Field(default="", max_length=200)
    country: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=6_000)
    founder_names: list[str] = Field(default_factory=list)
    contact_email: str | None = Field(default=None, max_length=320)
    notes: str = Field(default="", max_length=8_000)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("company_name", mode="before")
    @classmethod
    def strip_crm_company_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("website", "contact_email", mode="before")
    @classmethod
    def strip_optional_crm_identity(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("sector", "country", "description", "notes", mode="before")
    @classmethod
    def strip_optional_crm_text(cls, value: str | None) -> str:
        return value.strip() if value else ""


class CRMCompany(CRMCompanyCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class CRMPitchCreate(BaseModel):
    company_id: int = Field(gt=0)
    pitch_date: date
    deal_status: DealStatus = "new"
    funding_status: FundingStatus = "unknown"
    round_name: str = Field(default="", max_length=120)
    amount_requested_usd: float | None = Field(default=None, ge=0)
    source: str = Field(default="frontend_upload", max_length=120)
    notes: str = Field(default="", max_length=8_000)

    @field_validator("round_name", "source", "notes", mode="before")
    @classmethod
    def strip_pitch_text(cls, value: str | None) -> str:
        return value.strip() if value else ""


class CRMPitch(BaseModel):
    id: int
    company_id: int
    company_name: str
    company_website: str | None = None
    pitch_date: date
    deal_status: DealStatus
    funding_status: FundingStatus
    round_name: str = ""
    amount_requested_usd: float | None = None
    source: str = ""
    notes: str = ""
    created_at: datetime


class CRMRecordResult(BaseModel):
    recorded: bool = False
    company_id: int | None = None
    pitch_id: int | None = None


class CRMCountBucket(BaseModel):
    label: str
    count: int = Field(ge=0)


class CRMSummaryResponse(BaseModel):
    total_companies: int = 0
    total_pitches: int = 0
    deal_status_counts: list[CRMCountBucket] = Field(default_factory=list)
    funding_status_counts: list[CRMCountBucket] = Field(default_factory=list)
    monthly_pitch_counts: list[CRMCountBucket] = Field(default_factory=list)


class ScoreResult(BaseModel):
    novelty_score: int = Field(ge=0, le=100)
    market_score: int = Field(ge=0, le=100)
    competition_score: int = Field(ge=0, le=100)
    research_momentum_score: int = Field(ge=0, le=100)
    patent_originality_score: int = Field(ge=0, le=100)
    risk_level: Literal["low", "medium", "high"]


class StartupAnalysisResponse(ScoreResult):
    startup_name: str
    summary: str
    portfolio_check: PortfolioCheckResult = Field(default_factory=PortfolioCheckResult)
    crm_record: CRMRecordResult = Field(default_factory=CRMRecordResult)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
