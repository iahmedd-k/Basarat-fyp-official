from pydantic import BaseModel, Field


class IndexItem(BaseModel):
    index: str
    code: str
    current: float | None = None
    change: float | None = None
    change_pct: float | None = None
    high: float
    low: float


class IndicesResponse(BaseModel):
    indices: list[IndexItem]
    as_of: str | None = None
    is_stale: bool = True


class ConstituentItem(BaseModel):
    symbol: str
    name: str
    ldcp: float | None = None
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
    sector: str
    name: str | None = None
    ldcp: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    current: float
    change: float
    change_pct: float
    volume: int
    market_cap_m: float | None = None


class GainersResponse(BaseModel):
    gainers: list[MarketQuoteItem]
    as_of: str | None = None
    is_stale: bool = True


class LosersResponse(BaseModel):
    losers: list[MarketQuoteItem]
    as_of: str | None = None
    is_stale: bool = True


class VolumeSpikesResponse(BaseModel):
    volume_spikes: list[MarketQuoteItem]
    as_of: str | None = None
    is_stale: bool = True


class MarketQuotesResponse(BaseModel):
    stocks: list[MarketQuoteItem]
    total: int
    limit: int
    offset: int = 0
    filtered: bool = False
    as_of: str | None = None
    is_stale: bool = True


class SectorPerformance(BaseModel):
    sector: str
    avg_change_pct: float | None = None
    companies: int
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
    as_of: str | None = None
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
    as_of: str | None = None
    is_stale: bool = True
