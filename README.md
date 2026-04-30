# VC-Foresight

VC due-diligence MVP for novelty and long-term investability signal scoring.

The repository contains a production-style FastAPI backend in [startup-novelty-api](/Users/vigneshkumarselvaraj/Documents/VC-Foresight/startup-novelty-api/README.md) that evaluates startups using public web content, research signals, placeholder patent/search providers, and OpenRouter-based LLM extraction.

## Product Framing

This API is designed for:

- Novelty scoring
- Market attractiveness signal scoring
- Explainable VC diligence support

This API is not designed to:

- Predict with certainty whether a startup will survive 10 years
- Replace human investment judgment
- Act as investment advice

## What Was Built

The MVP includes:

- FastAPI app with `POST /score-startup`
- `GET /health` endpoint
- Pydantic request and response models
- Deterministic backend scoring logic
- Website homepage fetching with BeautifulSoup
- OpenAlex research lookup
- OpenRouter LLM extraction with JSON validation and fallback behavior
- Patent provider abstraction with placeholder implementation
- Competitor search abstraction with placeholder implementation
- Logging, timeouts, CORS, tests, `.env.example`, and Dockerfile

## Repository Layout

```text
VC-Foresight/
  README.md
  startup-novelty-api/
    app/
    tests/
    .env.example
    Dockerfile
    requirements.txt
    README.md
```

## Main API Input

`POST /score-startup`

```json
{
  "startup_name": "Example AI",
  "website": "https://example.com",
  "description": "AI platform for hospital workflow automation",
  "sector": "HealthTech AI",
  "country": "Germany"
}
```

## Main API Output

```json
{
  "startup_name": "Example AI",
  "novelty_score": 0,
  "market_score": 0,
  "competition_score": 0,
  "research_momentum_score": 0,
  "patent_originality_score": 0,
  "risk_level": "low",
  "summary": "Explainable diligence summary",
  "evidence": [
    {
      "source": "website",
      "finding": "Company messaging and extracted evidence",
      "url": "https://example.com"
    }
  ],
  "limitations": [
    "Any unavailable or placeholder sources are reported here."
  ]
}
```

## Scoring Logic

The final novelty score is computed in backend code, not delegated to the LLM.

Weighted novelty framework:

- `30%` technology uniqueness
- `25%` competitive whitespace
- `20%` research or patent originality
- `15%` market timing
- `10%` execution signal

The LLM is only used to extract structured signals such as:

- `product_category`
- `target_customer`
- `claimed_innovation`
- `competitors`
- `market_trends`
- `technical_keywords`
- `risks`

## Run Locally

```bash
cd /Users/vigneshkumarselvaraj/Documents/VC-Foresight/startup-novelty-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

## Environment Variables

Defined in [startup-novelty-api/.env.example](/Users/vigneshkumarselvaraj/Documents/VC-Foresight/startup-novelty-api/.env.example):

- `OPENROUTER_API_KEY=`
- `OPENROUTER_MODEL=`
- `APP_ENV=development`
- `HTTP_TIMEOUT_SECONDS=15`

## Verification

Implemented tests cover model validation and deterministic scoring logic.

Run:

```bash
cd /Users/vigneshkumarselvaraj/Documents/VC-Foresight/startup-novelty-api
pytest
```

## Notes

- The patent provider is currently a placeholder with neutral scoring.
- The competitor search provider is currently a placeholder with neutral scoring.
- The architecture is ready for later integration with PatentsView, SerpAPI, Brave Search, Tavily, Exa, Bing, or similar providers.
- Detailed implementation notes are in [startup-novelty-api/README.md](/Users/vigneshkumarselvaraj/Documents/VC-Foresight/startup-novelty-api/README.md).
