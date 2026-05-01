from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings
from app.utils.errors import ExternalServiceError


logger = logging.getLogger(__name__)


class OpenRouterClient:
    base_url = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self.http_client = http_client
        self.settings = settings

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 900,
        model: str | None = None,
    ) -> str:
        if not self.settings.openrouter_api_key:
            raise ExternalServiceError("OpenRouter API key is not configured.")

        payload = {
            "model": model or self.settings.openrouter_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        if self.settings.openrouter_http_referer:
            headers["HTTP-Referer"] = str(self.settings.openrouter_http_referer)
        if self.settings.openrouter_x_title:
            headers["X-Title"] = self.settings.openrouter_x_title

        for attempt in range(2):
            try:
                response = await self.http_client.post(self.base_url, headers=headers, json=payload)
                if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504} and attempt == 0:
                    logger.warning("Transient OpenRouter error %s, retrying once", response.status_code)
                    await asyncio.sleep(0.75)
                    continue
                response.raise_for_status()
                data = response.json()
                return self._extract_message_content(data)
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt == 0:
                    logger.warning("OpenRouter request failed (%s), retrying once", exc)
                    await asyncio.sleep(0.75)
                    continue
                raise ExternalServiceError(f"OpenRouter request failed: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                raise ExternalServiceError(
                    f"OpenRouter returned an error: {exc.response.status_code}"
                ) from exc

        raise ExternalServiceError("OpenRouter request failed after retry.")

    @staticmethod
    def _extract_message_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise ExternalServiceError("OpenRouter response did not include choices.")

        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            if text_parts:
                return "\n".join(text_parts)
        raise ExternalServiceError("OpenRouter response content was not parseable text.")
