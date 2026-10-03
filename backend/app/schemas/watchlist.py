from pydantic import BaseModel, Field


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Existing PSX stock symbol or exact company name (e.g. SYS or Systems Limited)",
    )
    target_price: float | None = Field(None, ge=0, description="Optional target price alert threshold")
    notes: str | None = Field(None, max_length=500, description="Optional personal notes for this symbol")


class WatchlistItemUpdate(BaseModel):
    target_price: float | None = Field(None, ge=0, description="Optional target price alert threshold")
    notes: str | None = Field(None, max_length=500, description="Optional personal notes for this symbol")


class WatchlistItemResponse(BaseModel):
    id: str
    watchlist_id: str
    stock_id: str | None = None
    symbol: str
    name: str | None = None
    sector: str | None = None
    target_price: float | None = None
    notes: str | None = None
    current_price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    is_stale: bool = False
    created_at: str
    updated_at: str


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the watchlist")
    description: str | None = Field(None, max_length=255, description="Optional description of the watchlist")
    is_default: bool = Field(False, description="Set as user's default watchlist")
    symbols: list[str] | None = Field(
        None,
        description="Optional initial list of existing PSX stock symbols or exact company names",
    )


class WatchlistUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100, description="Updated watchlist name")
    description: str | None = Field(None, max_length=255, description="Updated description")
    is_default: bool | None = Field(None, description="Set whether this watchlist is the default")


class WatchlistSummaryResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    is_default: bool = False
    item_count: int = 0
    created_at: str
    updated_at: str


class WatchlistDetailResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str | None = None
    is_default: bool = False
    items: list[WatchlistItemResponse] = []
    created_at: str
    updated_at: str


class WatchlistCheckResponse(BaseModel):
    symbol: str
    is_in_watchlist: bool
    watchlist_ids: list[str] = []
