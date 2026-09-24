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


class MarketQuoteItem(BaseModel):
    symbol: str
    sector: str
    ldcp: float
    open: float
    high: float
    low: float
    current: float
    change: float
    change_pct: float
    volume: int


class GainersResponse(BaseModel):
    gainers: list[MarketQuoteItem]


class LosersResponse(BaseModel):
    losers: list[MarketQuoteItem]


class VolumeSpikesResponse(BaseModel):
    volume_spikes: list[MarketQuoteItem]


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
    avg_change_pct: float
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
