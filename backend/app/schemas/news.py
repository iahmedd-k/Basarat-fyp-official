from typing import Optional
from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    key: str = ""
    name: str = ""
    type: str = "news"  # "official" | "news"


class SentimentInfo(BaseModel):
    label: str = "neutral"  # "bullish" | "bearish" | "neutral"
    score: float = 0.0
    method: str = "finbert"  # "finbert" | "eps_rule" | "none"


class SymbolInfo(BaseModel):
    symbol: str = ""
    name: str = ""


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


class NewsListResponse(BaseModel):
    items: list[NewsArticleResponse] = Field(default_factory=list)
    next_cursor: str = ""
    has_more: bool = False
    row: str = "news"  # "news" | "portfolio"
    last_updated_at: str = ""
    empty_reason: str = ""  # "", "no_holdings", "no_results"
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
    last_updated: str = ""
    refresh_available: bool = True
    next_refresh_at: str = ""
    articles_inserted: int = 0
    market_status: dict = Field(default_factory=dict)
    retry_after_seconds: int = 0


class NewsRefreshStatusResponse(BaseModel):
    state: str = "idle"  # "idle" | "running" | "done" | "failed"
    last_success_at: str = ""
    new_articles: int = 0


class SourceHealthResponse(BaseModel):
    key: str = ""
    name: str = ""
    type: str = "news"
    last_success_at: str = ""
    last_error: str = ""
    consecutive_failures: int = 0
    healthy: bool = True


class SourcesResponse(BaseModel):
    sources: list[SourceHealthResponse] = Field(default_factory=list)