from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "HealthTech": ("health", "healthcare", "hospital", "clinical", "patient", "medical", "medtech", "care"),
    "FinTech": ("fintech", "finance", "financial", "bank", "banking", "payments", "payment", "lending", "insurance"),
    "Climate & Energy": ("climate", "carbon", "battery", "renewable", "solar", "wind", "grid", "energy"),
    "Enterprise SaaS": ("enterprise", "workflow", "crm", "sales", "hr", "backoffice", "ops", "automation", "productivity"),
    "Developer Tools": ("developer", "devops", "infrastructure", "infra", "cloud", "api", "sdk", "engineering", "platform"),
    "Cybersecurity": ("security", "cyber", "identity", "threat", "siem", "zero trust", "fraud", "authentication"),
    "Commerce & Retail": ("ecommerce", "e-commerce", "retail", "merchant", "marketplace", "shopping", "conversion"),
    "Logistics & Mobility": ("logistics", "fleet", "shipping", "transport", "mobility", "warehouse", "supply chain"),
    "Education": ("education", "edtech", "learning", "students", "school", "curriculum", "tutoring"),
    "PropTech": ("real estate", "property", "leasing", "construction", "tenant", "building", "proptech"),
    "Biotech": ("biotech", "drug", "genomics", "therapeutic", "biology", "diagnostics", "pharma"),
    "Consumer": ("consumer", "creator", "social", "community", "gaming", "lifestyle", "travel"),
}

AI_KEYWORDS = ("ai", "artificial intelligence", "machine learning", "ml", "llm", "foundation model", "neural")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def truncate_text(value: str, limit: int) -> str:
    normalized = normalize_whitespace(value)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def extract_keywords(value: str, max_keywords: int = 8) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", value.lower())
    filtered = [token for token in tokens if token not in STOPWORDS]
    counts = Counter(filtered)
    return [token for token, _ in counts.most_common(max_keywords)]


def build_keyword_query(values: list[str], max_terms: int = 8) -> str:
    keywords = extract_keywords(" ".join(values), max_keywords=max_terms)
    return " ".join(keywords)


def extract_json_object(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Could not locate a JSON object in the model response.")

    snippet = cleaned[start : end + 1]
    parsed = json.loads(snippet)
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON was not an object.")
    return parsed


def predict_pitch_domain(*values: str) -> str:
    weighted_values: list[tuple[str, float]] = []
    for index, value in enumerate(values):
        normalized = normalize_whitespace(value).lower()
        if not normalized:
            continue
        weight = 3.0 if index == 0 else 2.0 if index == 1 else 1.0
        weighted_values.append((normalized, weight))

    if not weighted_values:
        return "General Software"

    scores = {domain: 0.0 for domain in DOMAIN_KEYWORDS}
    ai_score = 0.0
    for text, weight in weighted_values:
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    scores[domain] += weight
        for keyword in AI_KEYWORDS:
            if keyword in text:
                ai_score += weight

    top_domain, top_score = max(scores.items(), key=lambda item: item[1])
    if top_score <= 0:
        return "AI Infrastructure" if ai_score >= 3 else "General Software"

    if ai_score >= 3 and top_domain not in {"AI Infrastructure", "Biotech"}:
        return f"{top_domain} AI"
    return top_domain
