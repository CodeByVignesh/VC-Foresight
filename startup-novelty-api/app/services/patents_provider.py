from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import PatentMetrics, StartupScoreRequest


class PatentsProvider(ABC):
    @abstractmethod
    async def search(self, startup: StartupScoreRequest) -> PatentMetrics:
        raise NotImplementedError


class PlaceholderPatentsProvider(PatentsProvider):
    async def search(self, startup: StartupScoreRequest) -> PatentMetrics:
        return PatentMetrics(
            limitations=[
                "Patent search provider is a placeholder and returns neutral scoring.",
                "TODO: integrate PatentsView, Google Patents, or another patent search API.",
            ],
            provider_confidence=0.0,
        )
