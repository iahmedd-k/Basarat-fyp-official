from pydantic import BaseModel, Field
from typing import Optional


class SourceInfo(BaseModel):
    key: str
    name: str
    type: str  # "official" | "news"


class SentimentInfo(BaseModel):
    label: Optional[str] = None  # "bullish" | "bearish" | "neutral" | null
    score: Optional[float] = None
    method: Optional[str] = None  # "finbert" | "eps_rule" | "none"


class SymbolInfo(BaseModel):
    symbol: str
    name: Optional[str] = None


class NewsArticleResponse(BaseModel):
    id: str
    title: str
    url: str
    external_url: Optional[str] = None
    source: SourceInfo
    is_official: bool
    summary: Optional[str] = None
    symbols: list[SymbolInfo] = Field(default_factory=list)
    event_type: Optional[str] = None
    sentiment: Optional[SentimentInfo] = None
    impact_score: Optional[int] = None
    published_at: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class NewsListResponse(BaseModel):
    items: list[NewsArticleResponse]
    next_cursor: Optional[str] = None
    has_more: bool
    row: str  # "news" | "portfolio"
    last_updated_at: Optional[str] = None
    empty_reason: Optional[str] = None  # null, "no_holdings", "no_results"
    total: int = 0


class EventResponse(BaseModel):
    id: str
    event_type: str
    symbol: Optional[str] = None
    company_name: Optional[str] = None
    event_date: str
    title: str
    description: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None

    model_config = {"from_attributes": True}


class EventsCalendarResponse(BaseModel):
    items: list[EventResponse]
    total: int


class IngestResult(BaseModel):
    source: str
    articles_fetched: int = 0
    articles_inserted: int = 0
    articles_skipped_duplicate: int = 0
    articles_symbol_tagged: int = 0
    articles_sentiment_processed: int = 0
    error: Optional[str] = None


class NewsRefreshResponse(BaseModel):
    status: str  # "completed" | "skipped_cooldown" | "skipped_outside_hours" | "started" | "cooldown" | "already_running"
    last_updated: Optional[str] = None
    refresh_available: bool
    next_refresh_at: Optional[str] = None
    articles_inserted: int = 0
    market_status: dict = Field(default_factory=dict)
    retry_after_seconds: Optional[int] = None


class NewsRefreshStatusResponse(BaseModel):
    state: str  # "idle" | "running" | "done" | "failed"
    last_success_at: Optional[str] = None
    new_articles: int = 0


class SourceHealthResponse(BaseModel):
    key: str
    name: str
    type: str
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    healthy: bool = True


class SourcesResponse(BaseModel):
    sources: list[SourceHealthResponse]