from pydantic import BaseModel


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    sector: str | None = None


class StockSearchResponse(BaseModel):
    results: list[StockSearchResult]


class DayRange(BaseModel):
    low: float | None = None
    high: float | None = None


class StockOverview(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    ltp: float | None = None
    ldcp: float | None = None
    change: float | None = None
    change_pct: float | None = None
    day_range: DayRange
    volume: int | None = None
    market_cap_m: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    year_change_pct: float | None = None
    ytd_change_pct: float | None = None


class PriceBar(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class PriceHistoryResponse(BaseModel):
    symbol: str
    range: str
    bars: list[PriceBar]


class IndicatorSeries(BaseModel):
    date: str
    value: float | None = None


class TechnicalIndicatorsResponse(BaseModel):
    symbol: str
    period: int
    indicators: dict[str, list[IndicatorSeries]]


class FundamentalMetric(BaseModel):
    key: str
    value: float | None = None
    note: str


class FundamentalsExtras(BaseModel):
    year_change_pct: float | None = None
    ytd_change_pct: float | None = None
    gross_profit_margin_pct: float | None = None
    net_profit_margin_pct: float | None = None
    eps_growth_pct: float | None = None


class FundamentalsResponse(BaseModel):
    symbol: str
    metrics: list[FundamentalMetric]
    extras: FundamentalsExtras
