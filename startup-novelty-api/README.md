# Startup Novelty API

Novelty and long-term investability signal scoring for VC due diligence.

## What This API Does

This MVP analyzes a startup using:

- The startup website homepage
- An optional uploaded pitch deck or memo in `.pptx` or `.pdf`
- Optional meeting transcript notes
- VC CRM records for all pitched companies
- The VC's internal investment database
- Public research metadata from OpenAlex
- A patent provider abstraction
- A web search / competitor provider abstraction
- LLM-based structured extraction through OpenRouter

It produces explainable due-diligence signals for:

- `novelty_score`
- `market_score`
- `competition_score`
- `research_momentum_score`
- `patent_originality_score`
- `crm_record`
- `portfolio_check`
- `risk_level`

The final scores are computed by deterministic Python logic. The LLM is used for structured fact extraction and summarization support, not for directly deciding the final score.

## What This API Does Not Do

- It does not predict with certainty whether a startup will survive for 10 years.
- It does not replace partner judgment, founder interviews, customer diligence, or legal review.
- It does not yet include a production patent database integration or a real search API integration.

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic
- httpx
- OpenRouter
- BeautifulSoup
- pytest

## Project Structure

```text
startup-novelty-api/
  app/
    main.py
    config.py
    models.py
    scoring.py
    services/
      openrouter_client.py
      website_fetcher.py
      openalex_client.py
      patents_provider.py
      search_provider.py
      llm_extractor.py
    utils/
      text.py
      errors.py
  tests/
    test_scoring.py
    test_models.py
  .env.example
  requirements.txt
  README.md
  Dockerfile
```

## Setup

1. Create a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Set `OPENROUTER_API_KEY`.

```bash
cd startup-novelty-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Yes for LLM extraction | OpenRouter API key |
| `OPENROUTER_MODEL` | No | Model name, defaults to `openai/gpt-4.1-mini` |
| `APP_ENV` | No | Example: `development`, `production` |
| `HTTP_TIMEOUT_SECONDS` | No | Default request timeout for upstream APIs |
| `VC_PORTFOLIO_DB_PATH` | No | SQLite path shared by the VC portfolio and CRM databases |

Optional headers supported by the code:

- `OPENROUTER_HTTP_REFERER`
- `OPENROUTER_X_TITLE`
- `LOG_LEVEL`

## Running Locally

```bash
cd startup-novelty-api
uvicorn app.main:app --reload
```

Available endpoints:

- `GET /health`
- `GET /crm/companies`
- `POST /crm/companies`
- `GET /crm/pitches`
- `POST /crm/pitches`
- `GET /crm/summary`
- `GET /portfolio-companies`
- `POST /portfolio-companies`
- `POST /score-startup`
- `GET /docs`

## CRM Flow

The backend now supports a lightweight VC CRM for every company that pitches.

Stored company fields include:

- company name
- website
- sector
- country
- description
- founder names
- contact email
- internal notes
- keywords

Stored pitch fields include:

- pitch date
- deal status
- funding status
- round name
- amount requested
- source of the deal
- pitch notes

The intended flow is:

1. A startup is uploaded from the frontend.
2. The API can record the startup and pitch details into CRM.
3. The API checks the VC portfolio for internal overlap.
4. The API computes the novelty score.

This keeps CRM, portfolio overlap, and novelty scoring related but separate.

## Portfolio Database Flow

Before novelty scoring, the API checks the uploaded startup materials against the VC's internal portfolio database.

The sequence is:

1. The frontend uploads the startup website and optional diligence materials.
2. The backend compares the startup against stored portfolio companies in SQLite.
3. The API returns portfolio overlap signals such as exact, strong, or related matches.
4. The same startup context then flows into the novelty scoring pipeline.

This keeps internal portfolio overlap separate from market novelty while still returning both in one response.

## Portfolio Management API

Create a portfolio company:

```bash
curl -X POST http://127.0.0.1:8000/portfolio-companies \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Hospital Flow",
    "website": "https://hospitalflow.ai",
    "sector": "HealthTech AI",
    "country": "Germany",
    "thesis": "Workflow automation for hospitals",
    "keywords": ["hospital", "workflow", "automation"]
  }'
```

List portfolio companies:

```bash
curl http://127.0.0.1:8000/portfolio-companies
```

## CRM Management API

Create or update a CRM company:

```bash
curl -X POST http://127.0.0.1:8000/crm/companies \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Infra Brain",
    "website": "https://infra.example",
    "sector": "Developer Tools",
    "country": "Germany",
    "description": "AI infra for engineering teams",
    "founder_names": ["Alice"],
    "keywords": ["developer", "infrastructure", "ai"]
  }'
```

Create a pitch record:

```bash
curl -X POST http://127.0.0.1:8000/crm/pitches \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 1,
    "pitch_date": "2026-05-01",
    "deal_status": "partner_review",
    "funding_status": "in_discussion",
    "round_name": "Seed",
    "amount_requested_usd": 750000,
    "source": "warm_intro",
    "notes": "Strong technical team"
  }'
```

Fetch chart-ready summary data:

```bash
curl http://127.0.0.1:8000/crm/summary
```

## API Contract

`POST /score-startup` now accepts `multipart/form-data`.

Required field:

- `website`

Optional fields:

- `startup_name`
- `description`
- `sector`
- `country`
- `meeting_notes`
- `founder_names` as comma-separated text
- `contact_email`
- `pitch_date` as `YYYY-MM-DD`
- `deal_status`
- `funding_status`
- `round_name`
- `amount_requested_usd`
- `crm_notes`
- `crm_source`
- `record_in_crm`
- `supporting_document` as `.pdf` or `.pptx`

## Example Request

```bash
curl -X POST http://127.0.0.1:8000/score-startup \
  -F "website=https://example.com" \
  -F "startup_name=Example AI" \
  -F "sector=HealthTech AI" \
  -F "country=Germany" \
  -F "pitch_date=2026-05-01" \
  -F "deal_status=screening" \
  -F "funding_status=seeking" \
  -F "founder_names=Alice Doe,Bob Roe" \
  -F "meeting_notes=Founder says the wedge is hospital workflow automation with fast deployment." \
  -F "supporting_document=@./example-deck.pptx"
```

## Example Response

```json
{
  "startup_name": "Example AI",
  "novelty_score": 64,
  "market_score": 67,
  "competition_score": 50,
  "research_momentum_score": 61,
  "patent_originality_score": 50,
  "crm_record": {
    "recorded": true,
    "company_id": 14,
    "pitch_id": 52
  },
  "portfolio_check": {
    "checked": true,
    "portfolio_company_count": 24,
    "overlap_score": 76,
    "overlap_level": "strong",
    "has_similar_investment": true,
    "top_matches": [
      {
        "company_id": 4,
        "company_name": "Hospital Flow",
        "website": "https://hospitalflow.ai",
        "sector": "HealthTech AI",
        "overlap_score": 76,
        "match_type": "strong",
        "shared_keywords": ["automation", "hospital", "workflow"],
        "rationale": "Shared keywords: automation, hospital, workflow. Sector overlap is high."
      }
    ]
  },
  "risk_level": "medium",
  "summary": "Example AI shows moderate novelty signals in HealthTech AI with evidence of market interest and research activity, but the current MVP uses placeholder patent and competitor search providers.",
  "evidence": [
    {
      "source": "website",
      "finding": "Homepage messaging emphasizes AI platform for hospital workflow automation.",
      "url": "https://example.com"
    },
    {
      "source": "openalex",
      "finding": "Recent publications suggest ongoing research interest in sector-adjacent topics.",
      "url": "https://api.openalex.org/works"
    }
  ],
  "limitations": [
    "Patent search provider is a placeholder and returns neutral scoring.",
    "Competitor search provider is a placeholder and returns neutral scoring."
  ]
}
```

## Data Sources in This MVP

### Website Fetcher

- Fetches the provided homepage safely with timeout protection.
- Extracts title, meta description, and visible text using BeautifulSoup.

### Document Parser

- Accepts uploaded `.pdf` and `.pptx` files.
- Extracts readable text from pitch decks, memos, and other supporting materials.
- Returns partial results with a limitation if a document is empty, unsupported, or unreadable.

### Meeting Notes

- Accepts optional transcript or diligence notes as plain text form data.
- Feeds the notes into LLM extraction, evidence generation, and research query enrichment.

### VC Portfolio Database

- Stores the VC's previous investments in SQLite.
- Checks whether the uploaded startup is exact, strong, or related to existing portfolio companies.
- Returns the top matching internal investments before the novelty score is interpreted.

### VC CRM Database

- Stores all pitched companies, not just invested ones.
- Records funding pipeline status and pitch metadata.
- Exposes summary data that can directly support charts in a future UI.

### OpenAlex

- Queries the OpenAlex works API with sector and description keywords.
- Extracts publication counts, years, topics, and representative titles.

### Patents

- The current `PatentsProvider` is intentionally a placeholder.
- The architecture is ready for later integration with PatentsView, Google Patents, or another commercial patent API.

### Competitor Search

- The current `SearchProvider` is a placeholder.
- It is designed so SerpAPI, Brave Search, Tavily, Exa, or Bing can be plugged in later.

## Suggested OpenRouter Models

Use `OPENROUTER_MODEL` to choose the model that fits your budget and latency needs. A sensible low-cost default is:

- `openai/gpt-4.1-mini`

Depending on what is currently available in your OpenRouter account, you may also prefer:

- `openrouter/auto`
- Another low-cost JSON-capable model that your team has approved

## Adding Real Search APIs Later

1. Replace `PlaceholderSearchProvider` in [app/services/search_provider.py](/Users/vigneshkumarselvaraj/Documents/VC-Foresight/startup-novelty-api/app/services/search_provider.py).
2. Map results into `CompetitorMetrics` and `EvidenceItem`.
3. Set `provider_confidence` based on result quality and coverage.
4. Add provider-specific API keys to `.env`.
5. Expand unit tests to cover the new provider behavior.

For patent integration, follow the same pattern in [app/services/patents_provider.py](/Users/vigneshkumarselvaraj/Documents/VC-Foresight/startup-novelty-api/app/services/patents_provider.py).

## Testing

```bash
cd startup-novelty-api
pytest
```

## Ethical Disclaimer

This API is a due-diligence support tool, not investment advice. It is designed to surface novelty and long-term investability signals, not to guarantee startup success or predict survival with certainty.
