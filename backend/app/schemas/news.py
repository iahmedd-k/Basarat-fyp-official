from pydantic import BaseModel, Field


class NewsArticleResponse(BaseModel):
    id: str
    title: str
    url: str
    source: str | None = None
    source_type: str | None = None
    summary: str | None = None
    symbols: list[str] = Field(default_factory=list)
    company_names: list[str] = Field(default_factory=list)
    sector: str | None = None
    event_type: str | None = None
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    impact_score: int | None = None
    published_at: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class NewsListResponse(BaseModel):
    items: list[NewsArticleResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class EventResponse(BaseModel):
    id: str
    event_type: str
    symbol: str | None = None
    company_name: str | None = None
    event_date: str
    title: str
    description: str | None = None
    source: str | None = None
    source_url: str | None = None

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
    error: str | None = None


class NewsRefreshResponse(BaseModel):
    status: str  # "completed" | "skipped_cooldown" | "skipped_outside_hours"
    last_updated: str | None = None
    refresh_available: bool
    next_refresh_at: str | None = None
    articles_inserted: int = 0
    market_status: dict = Field(default_factory=dict)
