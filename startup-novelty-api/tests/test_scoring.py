from app.models import CompetitorMetrics, PatentMetrics, ResearchMetrics, StartupSignals
from app.scoring import CURRENT_YEAR, calculate_scores


def test_calculate_scores_rewards_stronger_signals() -> None:
    signals = StartupSignals(
        product_category="HealthTech AI",
        target_customer="Hospitals",
        claimed_innovation="AI workflow orchestration for clinical operations with hospital-specific automation",
        competitors=["Vendor A"],
        market_trends=["Hospital staffing shortages", "Automation demand", "Ambient clinical AI"],
        technical_keywords=["workflow", "hospital", "automation", "clinical", "orchestration"],
        risks=["Enterprise sales cycles"],
        evidence_summary=["Research momentum is increasing", "The website describes a focused automation product"],
        website_signal_present=True,
    )
    research = ResearchMetrics(
        recent_paper_count=6,
        publication_years=[
            CURRENT_YEAR,
            CURRENT_YEAR - 1,
            CURRENT_YEAR - 1,
            CURRENT_YEAR - 2,
            CURRENT_YEAR - 2,
            CURRENT_YEAR - 3,
            CURRENT_YEAR - 4,
        ],
        top_titles=["Paper 1", "Paper 2"],
        topics=["Healthcare AI", "Workflow optimization", "Clinical automation"],
        trend_ratio=1.0,
        latest_publication_year=CURRENT_YEAR,
        provider_confidence=0.9,
    )
    patents = PatentMetrics(
        similar_patent_count=1,
        close_match_count=0,
        distinct_cpc_codes=["G16H", "G06N"],
        provider_confidence=0.8,
    )
    competitors = CompetitorMetrics(
        competitor_count=2,
        close_competitor_count=1,
        named_competitors=["Vendor A", "Vendor B"],
        whitespace_score_hint=65,
        provider_confidence=0.8,
    )

    result = calculate_scores(signals, research, patents, competitors)

    assert result.novelty_score >= 60
    assert result.market_score >= 60
    assert result.patent_originality_score >= 60
    assert result.risk_level in {"low", "medium"}


def test_calculate_scores_stays_neutral_with_placeholder_sources() -> None:
    signals = StartupSignals(
        product_category="FinTech",
        claimed_innovation="Embedded finance platform",
        technical_keywords=["embedded", "finance"],
    )
    research = ResearchMetrics(provider_confidence=0.0)
    patents = PatentMetrics(provider_confidence=0.0)
    competitors = CompetitorMetrics(provider_confidence=0.0)

    result = calculate_scores(signals, research, patents, competitors)

    assert 35 <= result.competition_score <= 65
    assert 35 <= result.patent_originality_score <= 65
    assert 35 <= result.research_momentum_score <= 65
