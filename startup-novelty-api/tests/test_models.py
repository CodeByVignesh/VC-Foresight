from app.models import EvidenceItem, StartupAnalysisResponse, StartupScoreRequest


def test_request_model_accepts_optional_website() -> None:
    payload = StartupScoreRequest(
        startup_name="Example AI",
        website=" https://example.com ",
        description="AI platform for hospital workflow automation",
        sector="HealthTech AI",
        country="Germany",
    )

    assert payload.website == "https://example.com"


def test_response_model_validates_expected_shape() -> None:
    response = StartupAnalysisResponse(
        startup_name="Example AI",
        novelty_score=60,
        market_score=62,
        competition_score=50,
        research_momentum_score=58,
        patent_originality_score=50,
        risk_level="medium",
        summary="Summary",
        evidence=[EvidenceItem(source="website", finding="Test finding", url="https://example.com")],
        limitations=["Placeholder search provider used."],
    )

    assert response.startup_name == "Example AI"
    assert response.evidence[0].source == "website"
