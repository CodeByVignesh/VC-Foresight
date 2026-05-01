from __future__ import annotations

from datetime import datetime, timezone

from app.models import CompetitorMetrics, PatentMetrics, ResearchMetrics, ScoreResult, StartupSignals


CURRENT_YEAR = datetime.now(timezone.utc).year


def clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def to_ten_point_score(score: int) -> float:
    return round(score / 10, 1)


def blend_with_neutral(raw_score: float, confidence: float) -> int:
    return clamp_score((raw_score * confidence) + (50 * (1 - confidence)))


def calculate_research_momentum_score(metrics: ResearchMetrics) -> int:
    recent_years = [year for year in metrics.publication_years if year >= CURRENT_YEAR - 2]
    prior_years = [year for year in metrics.publication_years if CURRENT_YEAR - 5 <= year < CURRENT_YEAR - 2]

    volume_score = min(metrics.recent_paper_count * 9, 45)
    freshness_score = 0
    if metrics.latest_publication_year is not None:
        age = CURRENT_YEAR - metrics.latest_publication_year
        if age <= 1:
            freshness_score = 25
        elif age == 2:
            freshness_score = 18
        elif age <= 4:
            freshness_score = 10

    trend_signal = metrics.trend_ratio if metrics.publication_years else 0.0
    if metrics.publication_years:
        trend_signal = (trend_signal + (len(recent_years) - max(len(prior_years), 1))) / 2
    trend_score = max(0, min(20, 10 + (trend_signal * 6)))
    topic_score = min(len(metrics.topics) * 2, 10)
    raw_score = volume_score + freshness_score + trend_score + topic_score
    return blend_with_neutral(raw_score, metrics.provider_confidence)


def calculate_patent_originality_score(metrics: PatentMetrics) -> int:
    raw_score = 85 - (metrics.close_match_count * 12) - (metrics.similar_patent_count * 6)
    raw_score += min(len(metrics.distinct_cpc_codes) * 3, 12)
    return blend_with_neutral(raw_score, metrics.provider_confidence)


def calculate_competition_score(signals: StartupSignals, metrics: CompetitorMetrics) -> int:
    competitor_count = max(metrics.competitor_count, len(signals.competitors), len(metrics.named_competitors))
    raw_score = 85 - (metrics.close_competitor_count * 15) - (competitor_count * 5)
    raw_score += (metrics.whitespace_score_hint - 50) * 0.4
    return blend_with_neutral(raw_score, metrics.provider_confidence)


def calculate_market_score(signals: StartupSignals, research_metrics: ResearchMetrics, competition_score: int) -> int:
    trend_signal = min(len(signals.market_trends) * 12, 36)
    research_signal = min(research_metrics.recent_paper_count * 5, 25)
    freshness_signal = 0
    if research_metrics.latest_publication_year is not None:
        age = CURRENT_YEAR - research_metrics.latest_publication_year
        freshness_signal = 15 if age <= 1 else 8 if age <= 3 else 0
    whitespace_adjustment = 8 if competition_score >= 60 else 0 if competition_score >= 45 else -8
    raw_score = 30 + trend_signal + research_signal + freshness_signal + whitespace_adjustment
    return clamp_score(raw_score)


def calculate_execution_signal_score(signals: StartupSignals) -> int:
    raw_score = 30
    raw_score += 15 if signals.website_signal_present else 0
    raw_score += 15 if signals.target_customer else 0
    raw_score += 10 if signals.product_category else 0
    raw_score += 10 if signals.claimed_innovation else 0
    raw_score += min(len(signals.evidence_summary) * 4, 12)
    raw_score -= min(len(signals.risks) * 4, 20)
    return clamp_score(raw_score)


def calculate_technology_uniqueness_score(
    signals: StartupSignals,
    research_momentum_score: int,
    patent_originality_score: int,
) -> int:
    technical_depth = min(len(signals.technical_keywords) * 6, 24)
    innovation_score = 20 if len(signals.claimed_innovation.split()) >= 8 else 10 if signals.claimed_innovation else 0
    category_score = 8 if signals.product_category else 0
    evidence_score = min(len(signals.evidence_summary) * 3, 12)
    raw_score = 25 + technical_depth + innovation_score + category_score + evidence_score
    raw_score += (research_momentum_score - 50) * 0.15
    raw_score += (patent_originality_score - 50) * 0.25
    return clamp_score(raw_score)


def derive_risk_level(
    novelty_score: int,
    market_score: int,
    competition_score: int,
    research_momentum_score: int,
    signals: StartupSignals,
) -> str:
    risk_points = 0
    if novelty_score < 50:
        risk_points += 2
    elif novelty_score < 65:
        risk_points += 1
    if market_score < 45:
        risk_points += 1
    if competition_score < 40:
        risk_points += 1
    if research_momentum_score < 40:
        risk_points += 1
    if len(signals.risks) >= 4:
        risk_points += 1

    if risk_points >= 4:
        return "high"
    if risk_points >= 2:
        return "medium"
    return "low"


def calculate_fit_score(
    novelty_score: int,
    market_score: int,
    competition_score: int,
    execution_signal_score: int,
) -> int:
    return clamp_score(
        (execution_signal_score * 0.35)
        + (market_score * 0.30)
        + (competition_score * 0.20)
        + (novelty_score * 0.15)
    )


def calculate_foresight_score(
    novelty_score: int,
    market_score: int,
    research_momentum_score: int,
    patent_originality_score: int,
) -> int:
    return clamp_score(
        (market_score * 0.35)
        + (research_momentum_score * 0.30)
        + (patent_originality_score * 0.20)
        + (novelty_score * 0.15)
    )


def calculate_scores(
    signals: StartupSignals,
    research_metrics: ResearchMetrics,
    patent_metrics: PatentMetrics,
    competitor_metrics: CompetitorMetrics,
) -> ScoreResult:
    research_momentum_score = calculate_research_momentum_score(research_metrics)
    patent_originality_score = calculate_patent_originality_score(patent_metrics)
    competition_score = calculate_competition_score(signals, competitor_metrics)
    market_score = calculate_market_score(signals, research_metrics, competition_score)
    execution_signal_score = calculate_execution_signal_score(signals)
    technology_uniqueness_score = calculate_technology_uniqueness_score(
        signals=signals,
        research_momentum_score=research_momentum_score,
        patent_originality_score=patent_originality_score,
    )
    research_patent_originality_score = clamp_score(
        (research_momentum_score * 0.4) + (patent_originality_score * 0.6)
    )

    novelty_score = clamp_score(
        (technology_uniqueness_score * 0.30)
        + (competition_score * 0.25)
        + (research_patent_originality_score * 0.20)
        + (market_score * 0.15)
        + (execution_signal_score * 0.10)
    )
    fit_score = calculate_fit_score(
        novelty_score=novelty_score,
        market_score=market_score,
        competition_score=competition_score,
        execution_signal_score=execution_signal_score,
    )
    foresight_score = calculate_foresight_score(
        novelty_score=novelty_score,
        market_score=market_score,
        research_momentum_score=research_momentum_score,
        patent_originality_score=patent_originality_score,
    )

    risk_level = derive_risk_level(
        novelty_score=novelty_score,
        market_score=market_score,
        competition_score=competition_score,
        research_momentum_score=research_momentum_score,
        signals=signals,
    )

    return ScoreResult(
        novelty_score=novelty_score,
        novelty_score_10=to_ten_point_score(novelty_score),
        market_score=market_score,
        market_score_10=to_ten_point_score(market_score),
        competition_score=competition_score,
        competition_score_10=to_ten_point_score(competition_score),
        research_momentum_score=research_momentum_score,
        research_momentum_score_10=to_ten_point_score(research_momentum_score),
        patent_originality_score=patent_originality_score,
        patent_originality_score_10=to_ten_point_score(patent_originality_score),
        fit_score=fit_score,
        fit_score_10=to_ten_point_score(fit_score),
        foresight_score=foresight_score,
        foresight_score_10=to_ten_point_score(foresight_score),
        risk_level=risk_level,
    )
