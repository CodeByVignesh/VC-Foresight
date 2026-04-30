from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.models import WebsiteContent
from app.utils.errors import ExternalServiceError
from app.utils.text import normalize_whitespace, truncate_text


logger = logging.getLogger(__name__)


class WebsiteFetcher:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.http_client = http_client

    async def fetch(self, website_url: str | None) -> WebsiteContent:
        if not website_url:
            return WebsiteContent(limitations=["No website was provided for homepage analysis."])

        parsed = urlparse(website_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return WebsiteContent(
                url=website_url,
                limitations=[f"Website URL is invalid or unsupported: {website_url}"],
            )

        try:
            response = await self.http_client.get(
                website_url,
                follow_redirects=True,
                headers={"User-Agent": "VC-Foresight-MVP/1.0"},
            )
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning("Website fetch failed for %s: %s", website_url, exc)
            return WebsiteContent(
                url=website_url,
                limitations=[f"Website fetch failed for {website_url}: {exc}"],
            )

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return WebsiteContent(
                url=str(response.url),
                limitations=[f"Website content type is not HTML: {content_type or 'unknown'}"],
            )

        return self._parse_html(str(response.url), response.text)

    def _parse_html(self, url: str, html: str) -> WebsiteContent:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as exc:  # pragma: no cover - BeautifulSoup failures are rare
            raise ExternalServiceError(f"Website HTML parsing failed: {exc}") from exc

        title = normalize_whitespace(soup.title.string if soup.title and soup.title.string else "")
        meta_description_tag = soup.find("meta", attrs={"name": "description"})
        meta_description = normalize_whitespace(
            meta_description_tag.get("content", "") if meta_description_tag else ""
        )

        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.extract()

        visible_text = normalize_whitespace(" ".join(soup.stripped_strings))
        return WebsiteContent(
            url=url,
            title=title,
            meta_description=meta_description,
            text=truncate_text(visible_text, 12_000),
            fetched=True,
        )
