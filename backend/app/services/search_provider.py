from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import CompetitorMetrics, StartupScoreRequest


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, startup: StartupScoreRequest) -> CompetitorMetrics:
        raise NotImplementedError


class PlaceholderSearchProvider(SearchProvider):
    async def search(self, startup: StartupScoreRequest) -> CompetitorMetrics:
        return CompetitorMetrics(
            limitations=[
                "Competitor search provider is a placeholder and returns neutral scoring.",
                "TODO: integrate SerpAPI, Brave Search, Tavily, Exa, or Bing Search.",
            ],
            provider_confidence=0.0,
        )
