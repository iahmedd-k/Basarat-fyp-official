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


class IndicatorSummaryItem(BaseModel):
    value: float | None = None
    signal: str | None = None
    description: str | None = None
    signal_line: float | None = None
    lower: float | None = None
    mid: float | None = None
    upper: float | None = None
    trend_strength: str | None = None


class SignalsBreakdown(BaseModel):
    buy: int = 0
    neutral: int = 0
    sell: int = 0


class TechnicalSummary(BaseModel):
    rsi: IndicatorSummaryItem | None = None
    macd: IndicatorSummaryItem | None = None
    sma: IndicatorSummaryItem | None = None
    bollinger: IndicatorSummaryItem | None = None
    adx: IndicatorSummaryItem | None = None


class TechnicalIndicatorsResponse(BaseModel):
    symbol: str
    period: int
    overall_signal: str | None = None
    summary_message: str | None = None
    signals_breakdown: SignalsBreakdown | None = None
    summary: TechnicalSummary | None = None
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


class CompanyProfile(BaseModel):
    name: str | None = None
    sector: str | None = None
    business_description: str | None = None
    ceo: str | None = None
    chairperson: str | None = None
    company_secretary: str | None = None
    website: str | None = None
    address: str | None = None


class EquityProfile(BaseModel):
    market_cap_pkr: float | None = None
    market_cap_pkr_m: float | None = None
    total_shares: int | None = None
    free_float_shares: int | None = None
    free_float_pct: float | None = None


class FinancialRatios(BaseModel):
    pe_ratio: float | None = None
    peg_ratio: float | None = None
    eps: float | None = None
    eps_growth_pct: float | None = None
    net_profit_margin_pct: float | None = None
    gross_profit_margin_pct: float | None = None
    dividend_yield_pct: float | None = None


class TradingLimits(BaseModel):
    year_high: float | None = None
    year_low: float | None = None
    circuit_breaker_lower: float | None = None
    circuit_breaker_upper: float | None = None
    year_change_pct: float | None = None
    ytd_change_pct: float | None = None


class DividendHistoryItem(BaseModel):
    ex_date: str | None = None
    cash_amount: str | None = None
    record_date: str | None = None
    pay_date: str | None = None


class AnnouncementItem(BaseModel):
    date: str | None = None
    title: str | None = None
    pdf_link: str | None = None


class FundamentalsResponse(BaseModel):
    symbol: str
    company_profile: CompanyProfile | None = None
    equity_profile: EquityProfile | None = None
    financials_annual: list[dict] | None = None
    financials_quarterly: list[dict] | None = None
    ratios: FinancialRatios | None = None
    trading_limits: TradingLimits | None = None
    dividend_history: list[DividendHistoryItem] | None = None
    announcements: list[AnnouncementItem] | None = None
    metrics: list[FundamentalMetric] | None = None
    extras: FundamentalsExtras | None = None
