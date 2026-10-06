from typing import Optional
from pydantic import BaseModel, Field, field_validator


class StockSearchResult(BaseModel):
    symbol: str = ""
    name: str = ""
    sector: str = ""

    @field_validator("symbol", "name", "sector", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)


class StockSearchResponse(BaseModel):
    results: list[StockSearchResult] = Field(default_factory=list)


class DayRange(BaseModel):
    low: float = 0.0
    high: float = 0.0

    @field_validator("low", "high", mode="before")
    @classmethod
    def _clean_float(cls, v):
        return 0.0 if v is None else float(v)


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

    @field_validator("symbol", "name", "sector", "quote_as_of", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("current_price", "ltp", "ldcp", "change", "change_pct", "market_cap_m", "market_cap", "pe_ratio", "year_change_pct", "ytd_change_pct", mode="before")
    @classmethod
    def _clean_float(cls, v):
        return 0.0 if v is None else float(v)

    @field_validator("volume", mode="before")
    @classmethod
    def _clean_int(cls, v):
        return 0 if v is None else int(v)


class PriceBar(BaseModel):
    date: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

    @field_validator("date", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("open", "high", "low", "close", mode="before")
    @classmethod
    def _clean_float(cls, v):
        return 0.0 if v is None else float(v)

    @field_validator("volume", mode="before")
    @classmethod
    def _clean_int(cls, v):
        return 0 if v is None else int(v)


class PriceHistoryResponse(BaseModel):
    symbol: str = ""
    range: str = "1M"
    bars: list[PriceBar] = Field(default_factory=list)
    as_of_date: str = ""
    data_age_days: int = 0
    is_stale: bool = False

    @field_validator("symbol", "range", "as_of_date", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("data_age_days", mode="before")
    @classmethod
    def _clean_int(cls, v):
        return 0 if v is None else int(v)


class IndicatorSeries(BaseModel):
    date: str = ""
    value: float = 0.0

    @field_validator("date", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("value", mode="before")
    @classmethod
    def _clean_float(cls, v):
        return 0.0 if v is None else float(v)


class IndicatorSummaryItem(BaseModel):
    value: float = 0.0
    signal: str = "neutral"
    description: str = ""
    signal_line: float = 0.0
    lower: float = 0.0
    mid: float = 0.0
    upper: float = 0.0
    trend_strength: str = "moderate"

    @field_validator("signal", "description", "trend_strength", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("value", "signal_line", "lower", "mid", "upper", mode="before")
    @classmethod
    def _clean_float(cls, v):
        return 0.0 if v is None else float(v)


class SignalsBreakdown(BaseModel):
    buy: int = 0
    neutral: int = 0
    sell: int = 0

    @field_validator("buy", "neutral", "sell", mode="before")
    @classmethod
    def _clean_int(cls, v):
        return 0 if v is None else int(v)


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
    value: Optional[float] = None
    note: str = ""

    @field_validator("key", "note", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("value", mode="before")
    @classmethod
    def _clean_val(cls, v):
        return None if v is None else float(v)


class FundamentalsExtras(BaseModel):
    year_change_pct: Optional[float] = None
    ytd_change_pct: Optional[float] = None
    gross_profit_margin_pct: Optional[float] = None
    net_profit_margin_pct: Optional[float] = None
    eps_growth_pct: Optional[float] = None

    @field_validator("year_change_pct", "ytd_change_pct", "gross_profit_margin_pct", "net_profit_margin_pct", "eps_growth_pct", mode="before")
    @classmethod
    def _clean_float(cls, v):
        return None if v is None else float(v)


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

    @field_validator("name", "sector", "business_description", "ceo", "chairperson", "company_secretary", "website", "address", "psx_url", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)


class EquityProfile(BaseModel):
    market_cap_pkr: Optional[float] = None
    market_cap_pkr_m: Optional[float] = None
    total_shares: Optional[int] = None
    free_float_shares: Optional[int] = None
    free_float_pct: Optional[float] = None

    @field_validator("market_cap_pkr", "market_cap_pkr_m", "free_float_pct", mode="before")
    @classmethod
    def _clean_eq_float(cls, v):
        return None if v is None else float(v)

    @field_validator("total_shares", "free_float_shares", mode="before")
    @classmethod
    def _clean_eq_int(cls, v):
        return None if v is None else int(v)


class FinancialRatios(BaseModel):
    pe_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    eps: Optional[float] = None
    eps_growth_pct: Optional[float] = None
    net_profit_margin_pct: Optional[float] = None
    gross_profit_margin_pct: Optional[float] = None
    dividend_yield_pct: Optional[float] = None

    @field_validator("pe_ratio", "peg_ratio", "eps", "eps_growth_pct", "net_profit_margin_pct", "gross_profit_margin_pct", "dividend_yield_pct", mode="before")
    @classmethod
    def _clean_ratios(cls, v):
        return None if v is None else float(v)


class TradingLimits(BaseModel):
    year_high: Optional[float] = None
    year_low: Optional[float] = None
    circuit_breaker_lower: Optional[float] = None
    circuit_breaker_upper: Optional[float] = None
    year_change_pct: Optional[float] = None
    ytd_change_pct: Optional[float] = None

    @field_validator("year_high", "year_low", "circuit_breaker_lower", "circuit_breaker_upper", "year_change_pct", "ytd_change_pct", mode="before")
    @classmethod
    def _clean_limits(cls, v):
        return None if v is None else float(v)


class DividendHistoryItem(BaseModel):
    ex_date: str = ""
    cash_amount: str = ""
    record_date: str = ""
    pay_date: str = ""

    @field_validator("ex_date", "cash_amount", "record_date", "pay_date", mode="before")
    @classmethod
    def _clean_div_str(cls, v):
        return "" if v is None else str(v)


class AnnouncementItem(BaseModel):
    date: str = ""
    title: str = ""
    pdf_link: str = ""

    @field_validator("date", "title", "pdf_link", mode="before")
    @classmethod
    def _clean_ann_str(cls, v):
        return "" if v is None else str(v)


class FinancialReportItem(BaseModel):
    report_type: str = ""
    period_ended: str = ""
    posting_date: str = ""
    url: str = ""

    @field_validator("report_type", "period_ended", "posting_date", "url", mode="before")
    @classmethod
    def _clean_rep_str(cls, v):
        return "" if v is None else str(v)


class SectorPeerItem(BaseModel):
    symbol: str = ""
    name: str = ""
    current: Optional[float] = None
    ldcp: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None

    @field_validator("symbol", "name", mode="before")
    @classmethod
    def _clean_peer_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("current", "ldcp", "change_pct", mode="before")
    @classmethod
    def _clean_peer_float(cls, v):
        return None if v is None else float(v)

    @field_validator("volume", mode="before")
    @classmethod
    def _clean_peer_int(cls, v):
        return None if v is None else int(v)


class SectorOverview(BaseModel):
    sector: Optional[str] = None
    companies_count: Optional[int] = None
    avg_change_pct: Optional[float] = None
    advancing: Optional[int] = None
    declining: Optional[int] = None
    unchanged: Optional[int] = None
    stock: Optional[SectorPeerItem] = None
    stock_rank: Optional[int] = None
    top_gainers: list[SectorPeerItem] = Field(default_factory=list)
    top_losers: list[SectorPeerItem] = Field(default_factory=list)

    @field_validator("sector", mode="before")
    @classmethod
    def _clean_sec_str(cls, v):
        return None if v is None else str(v)

    @field_validator("companies_count", "advancing", "declining", "unchanged", "stock_rank", mode="before")
    @classmethod
    def _clean_sec_int(cls, v):
        return None if v is None else int(v)

    @field_validator("avg_change_pct", mode="before")
    @classmethod
    def _clean_sec_float(cls, v):
        return None if v is None else float(v)


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

    @field_validator("symbol", "data_status", "data_message", "psx_official_url", "financials_unit", mode="before")
    @classmethod
    def _clean_fund_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("financial_reports_count", mode="before")
    @classmethod
    def _clean_fund_int(cls, v):
        return 0 if v is None else int(v)
