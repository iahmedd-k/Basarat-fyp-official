from typing import Optional
from pydantic import BaseModel, Field


class StockSearchResult(BaseModel):
    symbol: str = ""
    name: str = ""
    sector: str = ""


class StockSearchResponse(BaseModel):
    results: list[StockSearchResult] = Field(default_factory=list)


class DayRange(BaseModel):
    low: float = 0.0
    high: float = 0.0


class StockOverview(BaseModel):
    symbol: str = ""
    name: str = ""
    sector: str = ""
    current_price: float = 0.0
    ltp: float = 0.0
    ldcp: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    day_range: DayRange = Field(default_factory=DayRange)
    volume: int = 0
    market_cap_m: float = 0.0
    market_cap: float = 0.0
    pe_ratio: float = 0.0
    year_change_pct: float = 0.0
    ytd_change_pct: float = 0.0
    quote_as_of: str = ""
    quote_is_stale: bool = False


class PriceBar(BaseModel):
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0


class PriceHistoryResponse(BaseModel):
    symbol: str = ""
    range: str = "1M"
    bars: list[PriceBar] = Field(default_factory=list)
    as_of_date: str = ""
    data_age_days: int = 0
    is_stale: bool = False


class IndicatorSeries(BaseModel):
    date: str = ""
    value: float = 0.0


class IndicatorSummaryItem(BaseModel):
    value: float = 0.0
    signal: str = "neutral"
    description: str = ""
    signal_line: float = 0.0
    lower: float = 0.0
    mid: float = 0.0
    upper: float = 0.0
    trend_strength: str = "moderate"


class SignalsBreakdown(BaseModel):
    buy: int = 0
    neutral: int = 0
    sell: int = 0


class TechnicalSummary(BaseModel):
    rsi: IndicatorSummaryItem = Field(default_factory=IndicatorSummaryItem)
    macd: IndicatorSummaryItem = Field(default_factory=IndicatorSummaryItem)
    sma: IndicatorSummaryItem = Field(default_factory=IndicatorSummaryItem)
    bollinger: IndicatorSummaryItem = Field(default_factory=IndicatorSummaryItem)
    adx: IndicatorSummaryItem = Field(default_factory=IndicatorSummaryItem)


class TechnicalIndicatorsResponse(BaseModel):
    symbol: str = ""
    period: int = 14
    as_of_date: str = ""
    data_age_days: int = 0
    is_stale: bool = False
    overall_signal: str = "NEUTRAL"
    summary_message: str = "Technical indicators computed"
    signals_breakdown: SignalsBreakdown = Field(default_factory=SignalsBreakdown)
    summary: TechnicalSummary = Field(default_factory=TechnicalSummary)
    indicators: dict[str, list[IndicatorSeries]] = Field(default_factory=dict)


class FundamentalMetric(BaseModel):
    key: str = ""
    value: float = 0.0
    note: str = ""


class FundamentalsExtras(BaseModel):
    year_change_pct: float = 0.0
    ytd_change_pct: float = 0.0
    gross_profit_margin_pct: float = 0.0
    net_profit_margin_pct: float = 0.0
    eps_growth_pct: float = 0.0


class CompanyProfile(BaseModel):
    name: str = ""
    sector: str = ""
    business_description: str = ""
    ceo: str = ""
    chairperson: str = ""
    company_secretary: str = ""
    website: str = ""
    address: str = ""
    psx_url: str = ""


class EquityProfile(BaseModel):
    market_cap_pkr: float = 0.0
    market_cap_pkr_m: float = 0.0
    total_shares: int = 0
    free_float_shares: int = 0
    free_float_pct: float = 0.0


class FinancialRatios(BaseModel):
    pe_ratio: float = 0.0
    peg_ratio: float = 0.0
    eps: float = 0.0
    eps_growth_pct: float = 0.0
    net_profit_margin_pct: float = 0.0
    gross_profit_margin_pct: float = 0.0
    dividend_yield_pct: float = 0.0


class TradingLimits(BaseModel):
    year_high: float = 0.0
    year_low: float = 0.0
    circuit_breaker_lower: float = 0.0
    circuit_breaker_upper: float = 0.0
    year_change_pct: float = 0.0
    ytd_change_pct: float = 0.0


class DividendHistoryItem(BaseModel):
    ex_date: str = ""
    cash_amount: str = ""
    record_date: str = ""
    pay_date: str = ""


class AnnouncementItem(BaseModel):
    date: str = ""
    title: str = ""
    pdf_link: str = ""


class FinancialReportItem(BaseModel):
    report_type: str = ""
    period_ended: str = ""
    posting_date: str = ""
    url: str = ""


class SectorPeerItem(BaseModel):
    symbol: str = ""
    name: str = ""
    current: float = 0.0
    ldcp: float = 0.0
    change_pct: float = 0.0
    volume: int = 0


class SectorOverview(BaseModel):
    sector: str = ""
    companies_count: int = 0
    avg_change_pct: float = 0.0
    advancing: int = 0
    declining: int = 0
    unchanged: int = 0
    stock: SectorPeerItem = Field(default_factory=SectorPeerItem)
    stock_rank: int = 1
    top_gainers: list[SectorPeerItem] = Field(default_factory=list)
    top_losers: list[SectorPeerItem] = Field(default_factory=list)


class FundamentalsResponse(BaseModel):
    symbol: str = ""
    data_status: str = "available"
    data_message: str = "Fundamental metrics loaded successfully"
    psx_official_url: str = "https://dps.psx.com.pk"
    company_profile: CompanyProfile = Field(default_factory=CompanyProfile)
    equity_profile: EquityProfile = Field(default_factory=EquityProfile)
    financials_annual: list[dict] = Field(default_factory=list)
    financials_quarterly: list[dict] = Field(default_factory=list)
    financials_unit: str = "PKR Millions"
    ratio_history: list[dict] = Field(default_factory=list)
    financial_reports: list[FinancialReportItem] = Field(default_factory=list)
    financial_reports_count: int = 0
    ratios: FinancialRatios = Field(default_factory=FinancialRatios)
    trading_limits: TradingLimits = Field(default_factory=TradingLimits)
    dividend_history: list[DividendHistoryItem] = Field(default_factory=list)
    announcements: list[AnnouncementItem] = Field(default_factory=list)
    metrics: list[FundamentalMetric] = Field(default_factory=list)
    extras: FundamentalsExtras = Field(default_factory=FundamentalsExtras)
    sector_overview: SectorOverview = Field(default_factory=SectorOverview)
