from typing import Optional
from pydantic import BaseModel, Field


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Existing PSX stock symbol or exact company name (e.g. SYS or Systems Limited)",
    )
    target_price: Optional[float] = Field(None, ge=0, description="Optional target price alert threshold")
    notes: Optional[str] = Field(None, max_length=500, description="Optional personal notes for this symbol")


class WatchlistItemUpdate(BaseModel):
    target_price: Optional[float] = Field(None, ge=0, description="Optional target price alert threshold")
    notes: Optional[str] = Field(None, max_length=500, description="Optional personal notes for this symbol")


class WatchlistItemResponse(BaseModel):
    id: str = ""
    watchlist_id: str = ""
    stock_id: str = ""
    symbol: str = ""
    name: str = ""
    sector: str = ""
    target_price: float = 0.0
    notes: str = ""
    current_price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: int = 0
    is_stale: bool = False
    created_at: str = ""
    updated_at: str = ""


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the watchlist")
    description: Optional[str] = Field(None, max_length=255, description="Optional description of the watchlist")
    is_default: bool = Field(False, description="Set as user's default watchlist")
    symbols: Optional[list[str]] = Field(
        None,
        description="Optional initial list of existing PSX stock symbols or exact company names",
    )


class WatchlistUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated watchlist name")
    description: Optional[str] = Field(None, max_length=255, description="Updated description")
    is_default: Optional[bool] = Field(None, description="Set whether this watchlist is the default")


class WatchlistSummaryResponse(BaseModel):
    id: str = ""
    user_id: str = ""
    name: str = ""
    description: str = ""
    is_default: bool = False
    item_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class WatchlistDetailResponse(BaseModel):
    id: str = ""
    user_id: str = ""
    name: str = ""
    description: str = ""
    is_default: bool = False
    items: list[WatchlistItemResponse] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class WatchlistCheckResponse(BaseModel):
    symbol: str = ""
    is_in_watchlist: bool = False
    watchlist_ids: list[str] = Field(default_factory=list)
