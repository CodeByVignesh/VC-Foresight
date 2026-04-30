from app.models import EvidenceItem, StartupAnalysisResponse, StartupScoreRequest


def test_request_model_requires_website_and_normalizes_optional_fields() -> None:
    payload = StartupScoreRequest(
        startup_name="Example AI",
        website=" https://example.com ",
        description=None,
        sector=None,
        country=None,
        meeting_notes=None,
    )

    assert payload.website == "https://example.com"
    assert payload.description == ""
    assert payload.sector == ""
    assert payload.country == ""
    assert payload.meeting_notes == ""


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
