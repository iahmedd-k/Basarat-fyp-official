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
    source_key: str  # e.g., "psx", "br", "dawn", "secp", "sbp", "ogra", "mof", "mettis"
    source_type: str  # "official" | "news"
    external_id: str | None = None
    external_url: str | None = None
    published_at: datetime | None = None
    published_at_estimated: bool = False
    summary: str | None = None
    content: str | None = None  # only if permitted
    symbols: list[str] = field(default_factory=list)
    company_names: list[str] = field(default_factory=list)
    event_type: str | None = None
    metadata: dict = field(default_factory=dict)


class NewsSource(Protocol):
    """Interface that every source adapter must satisfy."""

    source_name: str
    source_type: str

    def fetch(self, limit: int = 50) -> list[NormalizedArticle]:
        """Fetch latest articles.  Must handle errors internally and
        return an empty list on failure (never raise)."""
        ...


class SourceChangedError(Exception):
    """Raised when a source's response indicates a layout/maintenance change."""
    pass


class SourceDisabledError(Exception):
    """Raised when a source is disabled via config."""
    pass
