"""Base class and shared types for news source adapters."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class NormalizedArticle:
    """Source-agnostic article representation returned by all adapters."""

    title: str
    url: str
    source: str
    source_type: str  # "official" | "financial_media"
    published_at: datetime | None = None
    summary: str | None = None
    content: str | None = None  # only if permitted
    metadata: dict = field(default_factory=dict)


class NewsSource(Protocol):
    """Interface that every source adapter must satisfy."""

    source_name: str
    source_type: str

    def fetch(self, limit: int = 50) -> list[NormalizedArticle]:
        """Fetch latest articles.  Must handle errors internally and
        return an empty list on failure (never raise)."""
        ...
