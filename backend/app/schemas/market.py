from typing import Optional
from pydantic import BaseModel, Field


class IndexItem(BaseModel):
    index: str = ""
    code: str = ""
    current: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    high: float = 0.0
    low: float = 0.0


class IndicesResponse(BaseModel):
    indices: list[IndexItem] = Field(default_factory=list)
    as_of: str = ""
    is_stale: bool = True


class ConstituentItem(BaseModel):
    symbol: str = ""
    name: str = ""
    ldcp: float = 0.0
    current: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    weight_pct: float = 0.0
    index_points: float = 0.0
    volume: int = 0
    freefloat_m: float = 0.0
    market_cap_m: float = 0.0


class IndexConstituentsResponse(BaseModel):
    index: str = ""
    code: str = ""
    shariah_compliant: Optional[bool] = None
    constituents: list[ConstituentItem] = Field(default_factory=list)
    as_of: str = ""
    is_stale: bool = True


class MarketQuoteItem(BaseModel):
    symbol: str = ""
    sector: Optional[str] = None
    name: Optional[str] = None
    ldcp: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    current: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: int = 0
    market_cap_m: Optional[float] = None


class GainersResponse(BaseModel):
    gainers: list[MarketQuoteItem] = Field(default_factory=list)
    as_of: str = ""
    is_stale: bool = True


class LosersResponse(BaseModel):
    losers: list[MarketQuoteItem] = Field(default_factory=list)
    as_of: str = ""
    is_stale: bool = True


class VolumeSpikesResponse(BaseModel):
    volume_spikes: list[MarketQuoteItem] = Field(default_factory=list)
    as_of: str = ""
    is_stale: bool = True


class MarketQuotesResponse(BaseModel):
    stocks: list[MarketQuoteItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0
    filtered: bool = False
    as_of: str = ""
    is_stale: bool = True
    recommended_poll_seconds: int = 30
    transport_hint: str = "Prefer websocket; use rest_polling when WS is unavailable"


class LiveTransportInfo(BaseModel):
    primary: str = "websocket"
    fallback: str = "rest_polling"
    websocket_path: str = "/api/v1/ws"
    websocket_url: str = ""
    rest_quotes_path: str = "/api/v1/market/quotes"
    protocol_docs_path: str = "/api/v1/ws/protocol"
    recommended_rest_poll_seconds: int = 30
    session_refresh_seconds: int = 90
    protocol_version: str = "v1"


class MarketLiveResponse(BaseModel):
    """Android discovery endpoint: how to consume live PSX quotes (WS + REST fallback)."""

    market_status: str = "open"
    is_market_open: bool = True
    timezone: str = "Asia/Karachi"
    current_time_pkt: str = ""
    as_of: str = ""
    is_stale: bool = True
    quote_count: int = 0
    session_refresh_enabled: bool = True
    transport: LiveTransportInfo = Field(default_factory=LiveTransportInfo)
    android_integration: list[str] = Field(default_factory=list)


class SectorPerformance(BaseModel):
    sector: str = ""
    name: str = ""
    avg_change_pct: float = 0.0
    companies: int = 0
    stock_count: int = 0
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    total_volume: int = 0
    market_cap_m: float = 0.0
    top_gainer_symbol: str = ""
    top_loser_symbol: str = ""


class SectorPerformanceResponse(BaseModel):
    sectors: list[SectorPerformance] = Field(default_factory=list)
    total_sectors: int = 0
    total_companies: int = 0
    classified_companies: int = 0
    unclassified_companies: int = 0
    as_of: str = ""
    is_stale: bool = True


class SentimentOverview(BaseModel):
    market_mood: str = "neutral"
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    advance_decline_ratio: float = 1.0
    gainers_pct: float = 0.0
    losers_pct: float = 0.0
    sector_performance: list[SectorPerformance] = Field(default_factory=list)
    top_movers: list[MarketQuoteItem] = Field(default_factory=list)
    as_of: str = ""
    is_stale: bool = True


class CuratedStockItem(BaseModel):
    symbol: str = ""
    name: str = ""
    sector: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    dividend_yield_pct: float = 0.0
    return_1y_pct: float = 0.0
    pe_ratio: float = 0.0
    market_cap: str = ""
    volume_30d_avg: int = 0
    metric_value: float = 0.0
    metric_label: str = ""


class CuratedStocksResponse(BaseModel):
    category: str = ""
    title: str = ""
    description: str = ""
    total_count: int = 0
    items: list[CuratedStockItem] = Field(default_factory=list)
    as_of: str = ""
    is_stale: bool = False
