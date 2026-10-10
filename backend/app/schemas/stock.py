from datetime import date
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


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


class PriceOnDateResponse(BaseModel):
    symbol: str
    requested_date: str
    price_date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: int = 0
    is_fallback: bool = False
    status: str = "EXACT_MATCH"
    message: str = "Price fetched successfully"


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
    signal: str = "NEUTRAL"
    description: str = ""
    signal_line: float = 0.0
    lower: float = 0.0
    mid: float = 0.0
    middle: float = 0.0
    upper: float = 0.0
    trend_strength: str = "MODERATE"
    histogram: float = 0.0
    crossover: str = "NEUTRAL"
    current_price: float = 0.0
    bandwidth_pct: float = 0.0
    percent_b: float = 0.0
    position: str = "MID_BAND"
    plus_di: float = 0.0
    minus_di: float = 0.0
    trend_direction: str = "NEUTRAL"

    @field_validator("signal", "description", "trend_strength", "crossover", "position", "trend_direction", mode="before")
    @classmethod
    def _clean_str(cls, v):
        return "" if v is None else str(v)

    @field_validator(
        "value", "signal_line", "lower", "mid", "middle", "upper",
        "histogram", "current_price", "bandwidth_pct", "percent_b",
        "plus_di", "minus_di", mode="before"
    )
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


class TechnicalDataQuality(BaseModel):
    status: str = "complete"
    source: str = "PSX"
    missing_indicators: list[str] = Field(default_factory=list)
    calculated_indicators: list[str] = Field(default_factory=list)


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
    data_quality: TechnicalDataQuality = Field(default_factory=TechnicalDataQuality)


class FundamentalMetric(BaseModel):
    key: str = ""
    name: str = ""
    value: Optional[float] = None
    unit: str = ""
    note: str = ""
    description: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_metric(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        key = str(res.get("key") or res.get("name") or "")
        name = str(res.get("name") or key)
        note = str(res.get("note") or res.get("description") or "")
        description = str(res.get("description") or note)
        unit = str(res.get("unit") or "")
        val = res.get("value")
        val_clean = float(val) if val is not None and str(val).replace(".", "", 1).replace("-", "", 1).isdigit() else None
        return {
            "key": key,
            "name": name,
            "value": val_clean,
            "unit": unit,
            "note": note,
            "description": description,
        }


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


class SourceInfo(BaseModel):
    primary: str = "PSX"
    psx_official_url: str = ""
    last_updated: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_source(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        return {
            "primary": str(res.get("primary") or "PSX"),
            "psx_official_url": str(res.get("psx_official_url") or res.get("url") or ""),
            "last_updated": str(res.get("last_updated") or res.get("date") or ""),
        }


class CompanyProfile(BaseModel):
    name: str = ""
    sector: str = ""
    sub_sector: Optional[str] = None
    industry: str = ""
    business_description: str = ""
    ceo: str = ""
    chairperson: str = ""
    company_secretary: str = ""
    auditor: Optional[str] = None
    website: str = ""
    address: str = ""
    incorporation_date: Optional[str] = None
    listing_date: Optional[str] = None
    fiscal_year_end: Optional[str] = None
    is_shariah_compliant: Optional[bool] = None
    security_type: str = "equity"
    company_name: Optional[str] = None
    symbol: Optional[str] = None
    psx_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_profile(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        name = str(res.get("name") or res.get("company_name") or "")
        sector = str(res.get("sector") or res.get("industry") or "")
        industry = str(res.get("industry") or sector)
        return {
            "name": name,
            "company_name": name,
            "symbol": str(res.get("symbol") or ""),
            "sector": sector,
            "sub_sector": res.get("sub_sector"),
            "industry": industry,
            "business_description": str(res.get("business_description") or ""),
            "ceo": str(res.get("ceo") or ""),
            "chairperson": str(res.get("chairperson") or ""),
            "company_secretary": str(res.get("company_secretary") or ""),
            "auditor": res.get("auditor"),
            "website": str(res.get("website") or ""),
            "address": str(res.get("address") or ""),
            "incorporation_date": res.get("incorporation_date"),
            "listing_date": res.get("listing_date"),
            "fiscal_year_end": res.get("fiscal_year_end"),
            "is_shariah_compliant": res.get("is_shariah_compliant"),
            "security_type": str(res.get("security_type") or "equity"),
            "psx_url": str(res.get("psx_url") or ""),
        }


class ShareStructure(BaseModel):
    market_cap_pkr: Optional[float] = None
    total_shares: Optional[int] = None
    shares_outstanding: Optional[int] = None
    free_float_shares: Optional[int] = None
    free_float_pct: Optional[float] = None
    paid_up_capital_pkr: Optional[float] = None
    face_value_per_share: Optional[float] = None
    book_value_per_share: Optional[float] = None
    market_cap_pkr_m: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_share_structure(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").replace("%", "").strip())
            except (ValueError, TypeError): return None

        def _to_i(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return int(float(str(val).replace(",", "").strip()))
            except (ValueError, TypeError): return None

        mcap_pkr = _to_f("market_cap_pkr", "market_cap")
        mcap_m = _to_f("market_cap_pkr_m") or (round(mcap_pkr / 1_000_000, 2) if mcap_pkr else None)
        tot_shares = _to_i("total_shares", "shares_outstanding")
        return {
            "market_cap_pkr": mcap_pkr,
            "market_cap_pkr_m": mcap_m,
            "total_shares": tot_shares,
            "shares_outstanding": tot_shares,
            "free_float_shares": _to_i("free_float_shares"),
            "free_float_pct": _to_f("free_float_pct"),
            "paid_up_capital_pkr": _to_f("paid_up_capital_pkr") or (round(tot_shares * 10.0, 2) if tot_shares else None),
            "face_value_per_share": _to_f("face_value_per_share") or 10.0,
            "book_value_per_share": _to_f("book_value_per_share", "book_value"),
        }


# Legacy alias
EquityProfile = ShareStructure


class ValuationMetrics(BaseModel):
    share_price: Optional[float] = None
    pe_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    enterprise_value_pkr: Optional[float] = None
    earnings_yield_pct: Optional[float] = None
    dividend_yield_pct: Optional[float] = None
    book_value_per_share: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_val(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").replace("%", "").strip())
            except (ValueError, TypeError): return None

        pe = _to_f("pe_ratio")
        return {
            "share_price": _to_f("share_price", "current_price"),
            "pe_ratio": pe,
            "price_to_book": _to_f("price_to_book", "pb_ratio"),
            "peg_ratio": _to_f("peg_ratio"),
            "price_to_sales": _to_f("price_to_sales"),
            "ev_to_ebitda": _to_f("ev_to_ebitda"),
            "enterprise_value_pkr": _to_f("enterprise_value_pkr"),
            "earnings_yield_pct": _to_f("earnings_yield_pct") or (round(100.0 / pe, 2) if pe and pe > 0 else None),
            "dividend_yield_pct": _to_f("dividend_yield_pct"),
            "book_value_per_share": _to_f("book_value_per_share"),
        }


class ProfitabilityMetrics(BaseModel):
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    profit_before_tax: Optional[float] = None
    profit_after_tax: Optional[float] = None
    eps: Optional[float] = None
    gross_profit_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    operating_profit_margin_pct: Optional[float] = None
    net_profit_margin_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    roa_pct: Optional[float] = None
    roic_pct: Optional[float] = None
    ebitda_margin_pct: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_prof(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").replace("%", "").strip())
            except (ValueError, TypeError): return None

        op_m = _to_f("operating_margin_pct", "operating_profit_margin_pct")
        return {
            "revenue": _to_f("revenue", "sales"),
            "gross_profit": _to_f("gross_profit"),
            "operating_profit": _to_f("operating_profit"),
            "profit_before_tax": _to_f("profit_before_tax"),
            "profit_after_tax": _to_f("profit_after_tax", "net_profit"),
            "eps": _to_f("eps"),
            "gross_profit_margin_pct": _to_f("gross_profit_margin_pct"),
            "operating_margin_pct": op_m,
            "operating_profit_margin_pct": op_m,
            "net_profit_margin_pct": _to_f("net_profit_margin_pct"),
            "roe_pct": _to_f("roe_pct", "roe"),
            "roa_pct": _to_f("roa_pct", "roa"),
            "roic_pct": _to_f("roic_pct", "roic"),
            "ebitda_margin_pct": _to_f("ebitda_margin_pct"),
        }


class GrowthMetrics(BaseModel):
    revenue_growth_yoy_pct: Optional[float] = None
    profit_growth_yoy_pct: Optional[float] = None
    eps_growth_yoy_pct: Optional[float] = None
    revenue_cagr_3y_pct: Optional[float] = None
    profit_cagr_3y_pct: Optional[float] = None
    eps_cagr_3y_pct: Optional[float] = None
    quarterly_revenue_growth_yoy_pct: Optional[float] = None
    quarterly_profit_growth_yoy_pct: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_growth(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").replace("%", "").strip())
            except (ValueError, TypeError): return None

        return {
            "revenue_growth_yoy_pct": _to_f("revenue_growth_yoy_pct"),
            "profit_growth_yoy_pct": _to_f("profit_growth_yoy_pct"),
            "eps_growth_yoy_pct": _to_f("eps_growth_yoy_pct", "eps_growth_pct"),
            "revenue_cagr_3y_pct": _to_f("revenue_cagr_3y_pct"),
            "profit_cagr_3y_pct": _to_f("profit_cagr_3y_pct"),
            "eps_cagr_3y_pct": _to_f("eps_cagr_3y_pct"),
            "quarterly_revenue_growth_yoy_pct": _to_f("quarterly_revenue_growth_yoy_pct"),
            "quarterly_profit_growth_yoy_pct": _to_f("quarterly_profit_growth_yoy_pct"),
        }


class FinancialStatementItem(BaseModel):
    period: str = ""
    fiscal_year: Optional[Any] = None
    quarter: int = 0
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    profit_before_tax: Optional[float] = None
    tax_expense: Optional[float] = None
    profit_after_tax: Optional[float] = None
    eps: Optional[float] = None
    dividend_per_share: float = 0.0
    sales: Optional[float] = None
    net_profit: Optional[float] = None
    ebitda: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_stmt(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").strip())
            except (ValueError, TypeError): return None

        period = str(res.get("period") or res.get("Period") or res.get("fiscal_year") or res.get("Fiscal Year") or res.get("year") or "")
        fy = res.get("fiscal_year") or res.get("Fiscal Year") or (int("".join(filter(str.isdigit, period))) if any(c.isdigit() for c in period) else None)
        rev = _to_f("revenue", "sales")
        pat = _to_f("profit_after_tax", "net_profit")
        gp = _to_f("gross_profit")
        op = _to_f("operating_profit")
        cost = _to_f("cost_of_revenue") or ((round(rev - gp, 2)) if (rev and gp) else None)
        
        q = res.get("quarter")
        if q is None:
            if "Q1" in period: q = 1
            elif "Q2" in period: q = 2
            elif "Q3" in period: q = 3
            elif "Q4" in period: q = 4
            else: q = 0
            
        div_ps = _to_f("dividend_per_share")
        if div_ps is None:
            div_ps = 0.0

        return {
            "period": period,
            "fiscal_year": fy,
            "quarter": int(q),
            "revenue": rev,
            "cost_of_revenue": cost,
            "gross_profit": gp,
            "operating_profit": op,
            "profit_before_tax": _to_f("profit_before_tax"),
            "tax_expense": _to_f("tax_expense"),
            "profit_after_tax": pat,
            "eps": _to_f("eps"),
            "dividend_per_share": div_ps,
            "sales": rev,
            "net_profit": pat,
            "ebitda": _to_f("ebitda") or (round(op * 1.18, 2) if op else None),
        }


class FinancialStatements(BaseModel):
    unit: str = "PKR millions"
    annual: list[FinancialStatementItem] = Field(default_factory=list)
    quarterly: list[FinancialStatementItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_financials(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        return {
            "unit": str(res.get("unit") or "PKR millions"),
            "annual": res.get("annual") or [],
            "quarterly": res.get("quarterly") or [],
        }


class BalanceSheetItem(BaseModel):
    period: str = ""
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash_and_cash_equivalents: float = 0.0
    accounts_receivable: float = 0.0
    inventory: float = 0.0
    short_term_debt: float = 0.0
    long_term_debt: float = 0.0
    net_fixed_assets: Optional[float] = None
    retained_earnings: Optional[float] = None
    receivables: float = 0.0
    total_debt: float = 0.0
    working_capital: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _normalize_bs(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").strip())
            except (ValueError, TypeError): return None

        rec = _to_f("accounts_receivable", "receivables") or 0.0
        st_debt = _to_f("short_term_debt") or 0.0
        lt_debt = _to_f("long_term_debt") or 0.0
        tot_debt = _to_f("total_debt") or round(st_debt + lt_debt, 2)
        inv = _to_f("inventory") or 0.0
        cash = _to_f("cash_and_cash_equivalents") or 0.0
        wc = _to_f("working_capital") or round((rec + inv + cash) - st_debt, 2)
        return {
            "period": str(res.get("period") or ""),
            "total_assets": _to_f("total_assets"),
            "total_liabilities": _to_f("total_liabilities"),
            "total_equity": _to_f("total_equity"),
            "cash_and_cash_equivalents": cash,
            "accounts_receivable": rec,
            "receivables": rec,
            "inventory": inv,
            "short_term_debt": st_debt,
            "long_term_debt": lt_debt,
            "total_debt": tot_debt,
            "net_fixed_assets": _to_f("net_fixed_assets"),
            "retained_earnings": _to_f("retained_earnings"),
            "working_capital": wc,
        }


class BalanceSheetOverview(BaseModel):
    unit: str = "PKR millions"
    annual: list[BalanceSheetItem] = Field(default_factory=list)
    quarterly: list[BalanceSheetItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_bs_overview(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        if "annual" in res:
            return {
                "unit": str(res.get("unit") or "PKR millions"),
                "annual": res.get("annual") or [],
                "quarterly": res.get("quarterly") or [],
            }
        return {
            "unit": "PKR millions",
            "annual": [res],
            "quarterly": [],
        }


class CashFlowItem(BaseModel):
    period: str = ""
    operating_cash_flow: float = 0.0
    investing_cash_flow: float = 0.0
    financing_cash_flow: float = 0.0
    capital_expenditure: float = 0.0
    free_cash_flow: float = 0.0
    net_change_in_cash: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _normalize_cf(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").strip())
            except (ValueError, TypeError): return None

        ocf = _to_f("operating_cash_flow") or 0.0
        icf = _to_f("investing_cash_flow") or 0.0
        fcf = _to_f("financing_cash_flow") or 0.0
        capex = _to_f("capital_expenditure") or 0.0
        free_cf = _to_f("free_cash_flow") or round(ocf - capex, 2)
        net_cash = _to_f("net_change_in_cash") or round(ocf + icf + fcf, 2)
        return {
            "period": str(res.get("period") or ""),
            "operating_cash_flow": ocf,
            "investing_cash_flow": icf,
            "financing_cash_flow": fcf,
            "capital_expenditure": capex,
            "free_cash_flow": free_cf,
            "net_change_in_cash": net_cash,
        }


class CashFlowOverview(BaseModel):
    unit: str = "PKR millions"
    annual: list[CashFlowItem] = Field(default_factory=list)
    quarterly: list[CashFlowItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_cf_overview(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        if "annual" in res:
            return {
                "unit": str(res.get("unit") or "PKR millions"),
                "annual": res.get("annual") or [],
                "quarterly": res.get("quarterly") or [],
            }
        return {
            "unit": "PKR millions",
            "annual": [res],
            "quarterly": [],
        }


class FinancialRatios(BaseModel):
    pe_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    peg_ratio: Optional[float] = None
    eps: Optional[float] = None
    eps_growth_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    roa_pct: Optional[float] = None
    roic_pct: Optional[float] = None
    gross_profit_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    operating_profit_margin_pct: Optional[float] = None
    net_profit_margin_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    interest_coverage_ratio: Optional[float] = None
    interest_coverage: Optional[float] = None
    dividend_yield_pct: Optional[float] = None
    dividend_payout_ratio_pct: Optional[float] = None
    pb_ratio: Optional[float] = None
    book_value_per_share: Optional[float] = None
    asset_turnover: Optional[float] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_ratios(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").replace("%", "").strip())
            except (ValueError, TypeError): return None

        pb = _to_f("price_to_book", "pb_ratio")
        op_m = _to_f("operating_margin_pct", "operating_profit_margin_pct")
        int_cov = _to_f("interest_coverage_ratio", "interest_coverage")
        return {
            "pe_ratio": _to_f("pe_ratio"),
            "price_to_book": pb,
            "pb_ratio": pb,
            "peg_ratio": _to_f("peg_ratio"),
            "eps": _to_f("eps"),
            "eps_growth_pct": _to_f("eps_growth_pct"),
            "roe_pct": _to_f("roe_pct", "roe"),
            "roa_pct": _to_f("roa_pct", "roa"),
            "roic_pct": _to_f("roic_pct", "roic"),
            "gross_profit_margin_pct": _to_f("gross_profit_margin_pct"),
            "operating_margin_pct": op_m,
            "operating_profit_margin_pct": op_m,
            "net_profit_margin_pct": _to_f("net_profit_margin_pct"),
            "debt_to_equity": _to_f("debt_to_equity"),
            "debt_to_assets": _to_f("debt_to_assets"),
            "current_ratio": _to_f("current_ratio"),
            "quick_ratio": _to_f("quick_ratio"),
            "interest_coverage_ratio": int_cov,
            "interest_coverage": int_cov,
            "dividend_yield_pct": _to_f("dividend_yield_pct"),
            "dividend_payout_ratio_pct": _to_f("dividend_payout_ratio_pct", "payout_ratio_pct"),
            "book_value_per_share": _to_f("book_value_per_share", "book_value"),
            "asset_turnover": _to_f("asset_turnover"),
        }


class TradingLimits(BaseModel):
    year_high: Optional[float] = None
    year_low: Optional[float] = None
    circuit_breaker_lower: Optional[float] = None
    circuit_breaker_upper: Optional[float] = None
    year_change_pct: Optional[float] = None
    ytd_change_pct: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    current_price: Optional[float] = None
    ldcp: Optional[float] = None
    change_pct: Optional[float] = None

    @field_validator(
        "year_high", "year_low", "circuit_breaker_lower", "circuit_breaker_upper",
        "year_change_pct", "ytd_change_pct", "day_high", "day_low", "current_price",
        "ldcp", "change_pct", mode="before"
    )
    @classmethod
    def _clean_limits(cls, v):
        return None if v is None else float(v)


class DividendHistoryEntry(BaseModel):
    ex_date: str = ""
    record_date: str = ""
    pay_date: str = ""
    cash_dividend_per_share: str = "0.00 PKR"
    bonus_ratio: str = "0%"
    right_issue_ratio: str = "0%"
    cash_amount: str = "0.00 PKR"
    bonus_pct: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _normalize_div_entry(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        ex = res.get("ex_date") or res.get("EX-DIVIDEND DATE")
        rec = res.get("record_date") or res.get("RECORD DATE")
        pay = res.get("pay_date") or res.get("PAY DATE")
        amt = res.get("cash_dividend_per_share") or res.get("cash_amount") or res.get("CASH AMOUNT")
        bonus = res.get("bonus_pct") or res.get("BONUS")
        bonus_f = 0.0
        if bonus is not None:
            try:
                bonus_f = float(str(bonus).replace("%", "").strip())
            except (ValueError, TypeError):
                bonus_f = 0.0
        return {
            "ex_date": str(ex) if ex is not None else "",
            "record_date": str(rec) if rec is not None else "",
            "pay_date": str(pay) if pay is not None else "",
            "cash_dividend_per_share": str(amt) if amt is not None else "0.00 PKR",
            "cash_amount": str(amt) if amt is not None else "0.00 PKR",
            "bonus_ratio": str(res.get("bonus_ratio") or "0%"),
            "right_issue_ratio": str(res.get("right_issue_ratio") or "0%"),
            "bonus_pct": bonus_f,
        }


# Legacy alias
DividendHistoryItem = DividendHistoryEntry


class DividendOverview(BaseModel):
    current_dividend_per_share: Optional[float] = None
    dividend_yield_pct: Optional[float] = None
    payout_ratio_pct: Optional[float] = None
    dividend_growth_pct: Optional[float] = None
    dividend_cover: Optional[float] = None
    history: list[DividendHistoryEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_div_overview(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        def _to_f(key, alt=None):
            val = res.get(key) if res.get(key) is not None else (res.get(alt) if alt else None)
            if val is None: return None
            try: return float(str(val).replace(",", "").replace("%", "").strip())
            except (ValueError, TypeError): return None

        return {
            "current_dividend_per_share": _to_f("current_dividend_per_share"),
            "dividend_yield_pct": _to_f("dividend_yield_pct"),
            "payout_ratio_pct": _to_f("payout_ratio_pct"),
            "dividend_growth_pct": _to_f("dividend_growth_pct"),
            "dividend_cover": _to_f("dividend_cover"),
            "history": res.get("history") or [],
        }


class CorporateActionItem(BaseModel):
    date: str = ""
    title: str = ""
    ratio: str = ""
    announcement_url: str = ""


class CorporateActions(BaseModel):
    bonus_issues: list[dict[str, Any]] = Field(default_factory=list)
    right_issues: list[dict[str, Any]] = Field(default_factory=list)
    stock_splits: list[dict[str, Any]] = Field(default_factory=list)
    mergers: list[dict[str, Any]] = Field(default_factory=list)
    acquisitions: list[dict[str, Any]] = Field(default_factory=list)


class SectorSpecificMetrics(BaseModel):
    sector_type: str = "technology"
    sector_name: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)


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
    title: Optional[str] = None
    url: str = ""
    date: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_report(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        title = str(res.get("title") or "")
        date = str(res.get("date") or "")
        report_type = str(res.get("report_type") or title or "Financial Report")
        period_ended = str(res.get("period_ended") or date or "")
        posting_date = str(res.get("posting_date") or date or "")
        url = str(res.get("url") or res.get("pdf_link") or "")
        if not res.get("title"):
            res["title"] = f"{report_type} {period_ended}".strip() if period_ended else report_type
        if not res.get("date"):
            res["date"] = period_ended or posting_date
        res["report_type"] = report_type
        res["period_ended"] = period_ended
        res["posting_date"] = posting_date
        res["url"] = url
        return res


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
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator("volume", mode="before")
    @classmethod
    def _clean_peer_int(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None


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
        return None if v is None or v == "" else str(v)

    @field_validator("stock", mode="before")
    @classmethod
    def _clean_sec_stock(cls, v):
        if not isinstance(v, dict):
            return None
        return v

    @field_validator("companies_count", "advancing", "declining", "unchanged", "stock_rank", mode="before")
    @classmethod
    def _clean_sec_int(cls, v):
        if v is None or v == "":
            return None
        try:
            return int(float(v))
        except (ValueError, TypeError):
            return None

    @field_validator("avg_change_pct", mode="before")
    @classmethod
    def _clean_sec_float(cls, v):
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class DataQuality(BaseModel):
    status: str = "complete"
    data_status: Optional[str] = "complete"
    data_message: Optional[str] = "Company fundamentals loaded successfully."
    missing_sections: list[str] = Field(default_factory=list)
    calculated_fields: list[str] = Field(default_factory=list)
    unavailable_fields: list[str] = Field(default_factory=list)
    last_audited_at: Optional[str] = ""
    source_authenticity: Optional[str] = "PSX DPS Direct & Financials Ingestion"
    psx_official_url: Optional[str] = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_dq(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        st = str(res.get("status") or res.get("data_status") or "complete")
        return {
            "status": st,
            "data_status": st,
            "data_message": str(res.get("data_message") or "Company fundamentals loaded successfully."),
            "missing_sections": res.get("missing_sections") or [],
            "calculated_fields": res.get("calculated_fields") or [],
            "unavailable_fields": res.get("unavailable_fields") or [],
            "last_audited_at": str(res.get("last_audited_at") or ""),
            "source_authenticity": str(res.get("source_authenticity") or "PSX DPS Direct & Financials Ingestion"),
            "psx_official_url": str(res.get("psx_official_url") or ""),
        }


class FundamentalsResponse(BaseModel):
    symbol: str = ""
    data_status: str = "complete"
    data_message: str = "Company fundamentals loaded successfully."
    source: SourceInfo = Field(default_factory=SourceInfo)
    company_profile: CompanyProfile = Field(default_factory=CompanyProfile)
    share_structure: ShareStructure = Field(default_factory=ShareStructure)
    valuation: ValuationMetrics = Field(default_factory=ValuationMetrics)
    profitability: ProfitabilityMetrics = Field(default_factory=ProfitabilityMetrics)
    growth: GrowthMetrics = Field(default_factory=GrowthMetrics)
    financials: FinancialStatements = Field(default_factory=FinancialStatements)
    balance_sheet: BalanceSheetOverview = Field(default_factory=BalanceSheetOverview)
    cash_flow: CashFlowOverview = Field(default_factory=CashFlowOverview)
    ratios: FinancialRatios = Field(default_factory=FinancialRatios)
    dividends: DividendOverview = Field(default_factory=DividendOverview)
    corporate_actions: CorporateActions = Field(default_factory=CorporateActions)
    sector_specific: SectorSpecificMetrics = Field(default_factory=SectorSpecificMetrics)
    financial_reports: list[FinancialReportItem] = Field(default_factory=list)
    data_quality: DataQuality = Field(default_factory=DataQuality)

    # Backwards compatibility fields for legacy clients and audit suites
    trading_limits: TradingLimits = Field(default_factory=TradingLimits)
    financial_reports_count: int = 0
    sector_overview: SectorOverview = Field(default_factory=SectorOverview)
    psx_official_url: str = "https://dps.psx.com.pk"
    equity_profile: Optional[ShareStructure] = None
    financials_annual: list[dict] = Field(default_factory=list)
    financials_quarterly: list[dict] = Field(default_factory=list)
    financials_unit: str = "PKR Millions"
    ratio_history: list[dict] = Field(default_factory=list)
    dividend_history: list[DividendHistoryEntry] = Field(default_factory=list)
    announcements: list[AnnouncementItem] = Field(default_factory=list)
    metrics: list[FundamentalMetric] = Field(default_factory=list)
    extras: FundamentalsExtras = Field(default_factory=FundamentalsExtras)

    @model_validator(mode="before")
    @classmethod
    def _sync_backwards_compatible_fields(cls, v):
        if not isinstance(v, dict):
            return v
        res = dict(v)
        symbol = str(res.get("symbol") or "")
        if "source" not in res:
            res["source"] = {
                "primary": "PSX",
                "psx_official_url": res.get("psx_official_url") or f"https://dps.psx.com.pk/company/{symbol}",
                "last_updated": date.today().isoformat(),
            }
        if "equity_profile" in res and "share_structure" not in res:
            res["share_structure"] = res["equity_profile"]
        elif "share_structure" in res and "equity_profile" not in res:
            res["equity_profile"] = res["share_structure"]
        if "data_quality" not in res:
            res["data_quality"] = {
                "status": res.get("data_status") or "complete",
                "data_status": res.get("data_status") or "complete",
                "data_message": res.get("data_message") or "Company fundamentals loaded successfully.",
                "missing_sections": [],
                "calculated_fields": [],
                "unavailable_fields": [],
                "last_audited_at": "",
                "source_authenticity": "PSX DPS Direct & Financials Ingestion",
                "psx_official_url": res.get("psx_official_url") or f"https://dps.psx.com.pk/company/{symbol}",
            }
        fin_reports = res.get("financial_reports")
        if isinstance(fin_reports, dict):
            flat = []
            for val in fin_reports.values():
                if isinstance(val, list):
                    flat.extend(val)
                elif isinstance(val, dict):
                    flat.append(val)
            res["financial_reports"] = flat
        elif not isinstance(fin_reports, list):
            res["financial_reports"] = []
        return res

    @field_validator("symbol", "data_status", "data_message", "psx_official_url", "financials_unit", mode="before")
    @classmethod
    def _clean_fund_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("financial_reports_count", mode="before")
    @classmethod
    def _clean_fund_int(cls, v):
        return 0 if v is None else int(v)

