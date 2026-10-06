from typing import Optional
from pydantic import BaseModel, Field, field_validator


class SourceInfo(BaseModel):
    key: str = ""
    name: str = ""
    type: str = "news"  # "official" | "news"


class SentimentInfo(BaseModel):
    label: str = "neutral"  # "bullish" | "bearish" | "neutral"
    score: float = 0.0
    method: str = "finbert"  # "finbert" | "eps_rule" | "none"

    @field_validator("label", mode="before")
    @classmethod
    def _clean_label(cls, v):
        return "neutral" if v is None else str(v)

    @field_validator("method", mode="before")
    @classmethod
    def _clean_method(cls, v):
        return "finbert" if v is None else str(v)

    @field_validator("score", mode="before")
    @classmethod
    def _clean_score(cls, v):
        return 0.0 if v is None else float(v)


class SymbolInfo(BaseModel):
    symbol: str = ""
    name: str = ""

    @field_validator("symbol", "name", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)


class NewsArticleResponse(BaseModel):
    id: str = ""
    title: str = ""
    url: str = ""
    external_url: str = ""
    source: SourceInfo = Field(default_factory=SourceInfo)
    is_official: bool = False
    summary: str = ""
    symbols: list[SymbolInfo] = Field(default_factory=list)
    event_type: str = ""
    sentiment: SentimentInfo = Field(default_factory=SentimentInfo)
    impact_score: int = 0
    published_at: str = ""
    created_at: str = ""

    model_config = {"from_attributes": True}

    @field_validator("id", "title", "url", "external_url", "summary", "event_type", "published_at", "created_at", mode="before")
    @classmethod
    def _clean_news_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("impact_score", mode="before")
    @classmethod
    def _clean_news_int(cls, v):
        return 0 if v is None else int(v)

    @field_validator("is_official", mode="before")
    @classmethod
    def _clean_news_bool(cls, v):
        return False if v is None else bool(v)

    @field_validator("sentiment", mode="before")
    @classmethod
    def _clean_news_sentiment(cls, v):
        if v is None:
            return SentimentInfo()
        return v


class NewsListResponse(BaseModel):
    items: list[NewsArticleResponse] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    has_more: bool = False
    row: str = "news"  # "news" | "portfolio"
    last_updated_at: Optional[str] = None
    empty_reason: Optional[str] = None  # "", "no_holdings", "no_results"
    total: int = 0


class EventResponse(BaseModel):
    id: str = ""
    event_type: str = ""
    symbol: str = ""
    company_name: str = ""
    event_date: str = ""
    title: str = ""
    description: str = ""
    source: str = ""
    source_url: str = ""

    model_config = {"from_attributes": True}


class EventsCalendarResponse(BaseModel):
    items: list[EventResponse] = Field(default_factory=list)
    total: int = 0


class IngestResult(BaseModel):
    source: str = ""
    articles_fetched: int = 0
    articles_inserted: int = 0
    articles_skipped_duplicate: int = 0
    articles_symbol_tagged: int = 0
    articles_sentiment_processed: int = 0
    error: str = ""


class NewsRefreshResponse(BaseModel):
    status: str = "completed"  # "completed" | "skipped_cooldown" | "skipped_outside_hours" | "started" | "cooldown" | "already_running"
    last_updated: Optional[str] = None
    refresh_available: bool = True
    next_refresh_at: Optional[str] = None
    articles_inserted: int = 0
    market_status: dict = Field(default_factory=dict)
    retry_after_seconds: int = 0

    @field_validator("last_updated", "next_refresh_at", mode="before")
    @classmethod
    def _clean_dt_str(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            from datetime import datetime, timezone
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
        return str(v)


class NewsRefreshStatusResponse(BaseModel):
    state: str = "idle"  # "idle" | "running" | "done" | "failed"
    last_success_at: Optional[str] = None
    new_articles: int = 0

    @field_validator("last_success_at", mode="before")
    @classmethod
    def _clean_opt_str(cls, v):
        return None if v is None else str(v)


class SourceHealthResponse(BaseModel):
    key: str = ""
    name: str = ""
    type: str = "news"
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    healthy: bool = True

    @field_validator("key", "name", "type", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("last_success_at", "last_error", mode="before")
    @classmethod
    def _clean_opt_str(cls, v):
        return None if v is None else str(v)

    @field_validator("consecutive_failures", mode="before")
    @classmethod
    def _clean_int(cls, v):
        return 0 if v is None else int(v)

    @field_validator("healthy", mode="before")
    @classmethod
    def _clean_bool(cls, v):
        return bool(v) if v is not None else True


class SourcesResponse(BaseModel):
    sources: list[SourceHealthResponse] = Field(default_factory=list)