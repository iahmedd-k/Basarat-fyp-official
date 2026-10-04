from pydantic import BaseModel, Field


class IndexItem(BaseModel):
    index: str
    code: str
    current: float
    change: float
    change_pct: float
    high: float
    low: float


class IndicesResponse(BaseModel):
    indices: list[IndexItem]
    as_of: str | None = None
    is_stale: bool = True


class ConstituentItem(BaseModel):
    symbol: str
    name: str
    ldcp: float
    current: float
    change: float
    change_pct: float
    weight_pct: float
    index_points: float
    volume: int
    freefloat_m: float
    market_cap_m: float


class IndexConstituentsResponse(BaseModel):
    index: str
    code: str
    shariah_compliant: bool | None = None
    constituents: list[ConstituentItem]
    as_of: str | None = None
    is_stale: bool = True


class MarketQuoteItem(BaseModel):
    symbol: str
    sector: str | None = None
    name: str | None = None
    ldcp: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    current: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int = 0
    market_cap_m: float | None = None


class GainersResponse(BaseModel):
    gainers: list[MarketQuoteItem]
    as_of: str = ""
    is_stale: bool = True


class LosersResponse(BaseModel):
    losers: list[MarketQuoteItem]
    as_of: str = ""
    is_stale: bool = True


class VolumeSpikesResponse(BaseModel):
    volume_spikes: list[MarketQuoteItem]
    as_of: str = ""
    is_stale: bool = True


class MarketQuotesResponse(BaseModel):
    stocks: list[MarketQuoteItem]
    total: int
    limit: int
    offset: int = 0
    filtered: bool = False
    as_of: str = ""
    is_stale: bool = True
    recommended_poll_seconds: int = 30
    transport_hint: str = "Prefer websocket; use rest_polling when WS is unavailable"


class LiveTransportInfo(BaseModel):
    primary: str = "websocket"
    fallback: str = "rest_polling"
    websocket_path: str
    websocket_url: str = ""
    rest_quotes_path: str
    protocol_docs_path: str
    recommended_rest_poll_seconds: int
    session_refresh_seconds: int
    protocol_version: str


class MarketLiveResponse(BaseModel):
    """Android discovery endpoint: how to consume live PSX quotes (WS + REST fallback)."""

    market_status: str
    is_market_open: bool
    timezone: str = "Asia/Karachi"
    current_time_pkt: str = ""
    as_of: str = ""
    is_stale: bool = True
    quote_count: int = 0
    session_refresh_enabled: bool = True
    transport: LiveTransportInfo
    android_integration: list[str] = Field(default_factory=list)


class SectorPerformance(BaseModel):
    sector: str
    name: str | None = None
    avg_change_pct: float | None = None
    companies: int = 0
    stock_count: int | None = None
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    total_volume: int = 0
    market_cap_m: float | None = None
    top_gainer_symbol: str | None = None
    top_loser_symbol: str | None = None


class SectorPerformanceResponse(BaseModel):
    sectors: list[SectorPerformance]
    total_sectors: int
    total_companies: int
    classified_companies: int
    unclassified_companies: int
    as_of: str = ""
    is_stale: bool = True


class SentimentOverview(BaseModel):
    market_mood: str
    advancing: int
    declining: int
    unchanged: int
    advance_decline_ratio: float
    gainers_pct: float
    losers_pct: float
    sector_performance: list[SectorPerformance]
    top_movers: list[MarketQuoteItem]
    as_of: str = ""
    is_stale: bool = True


class CuratedStockItem(BaseModel):
    symbol: str
    name: str | None = None
    sector: str | None = None
    price: float | None = None
    change_pct: float | None = None
    dividend_yield_pct: float | None = None
    return_1y_pct: float | None = None
    pe_ratio: float | None = None
    market_cap: str | None = None
    volume_30d_avg: int | None = None
    metric_value: float | None = None
    metric_label: str | None = None


class CuratedStocksResponse(BaseModel):
    category: str
    title: str
    description: str
    total_count: int
    items: list[CuratedStockItem]
    as_of: str | None = None
    is_stale: bool = False
