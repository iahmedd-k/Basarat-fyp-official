from typing import Optional
from pydantic import BaseModel, Field, field_validator


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

    @field_validator("id", "watchlist_id", "stock_id", "symbol", "name", "sector", "notes", "created_at", "updated_at", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("target_price", "current_price", "change", "change_pct", "high", "low", mode="before")
    @classmethod
    def _clean_float(cls, v):
        return 0.0 if v is None else float(v)

    @field_validator("volume", mode="before")
    @classmethod
    def _clean_int(cls, v):
        return 0 if v is None else int(v)

    @field_validator("is_stale", mode="before")
    @classmethod
    def _clean_bool(cls, v):
        return False if v is None else bool(v)


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

    @field_validator("id", "user_id", "name", "description", "created_at", "updated_at", mode="before")
    @classmethod
    def _clean_summary_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("item_count", mode="before")
    @classmethod
    def _clean_item_count(cls, v):
        return 0 if v is None else int(v)


class WatchlistDetailResponse(BaseModel):
    id: str = ""
    user_id: str = ""
    name: str = ""
    description: str = ""
    is_default: bool = False
    items: list[WatchlistItemResponse] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @field_validator("id", "user_id", "name", "description", "created_at", "updated_at", mode="before")
    @classmethod
    def _clean_detail_str(cls, v):
        return "" if v is None else str(v)


class WatchlistCheckResponse(BaseModel):
    symbol: str = ""
    is_in_watchlist: bool = False
    watchlist_ids: list[str] = Field(default_factory=list)
