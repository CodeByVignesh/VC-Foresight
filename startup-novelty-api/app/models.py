from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StartupScoreRequest(BaseModel):
    startup_name: str = Field(min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    description: str = Field(min_length=10, max_length=4_000)
    sector: str = Field(min_length=2, max_length=200)
    country: str = Field(min_length=2, max_length=100)

    @field_validator("startup_name", "description", "sector", "country", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("website", mode="before")
    @classmethod
    def strip_optional_website(cls, value: str | None) -> str | None:
        return value.strip() if value else value


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
    evidence: list[EvidenceItem] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
