package com.fyp.basarattradeinvest.data.remote.dto.stocks

import com.google.gson.JsonElement
import com.google.gson.annotations.SerializedName

data class FundamentalsResponseDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("data_status") val dataStatus: String? = null,
    @SerializedName("data_message") val dataMessage: String? = null,
    @SerializedName("source") val source: FundamentalsSourceDto? = null,
    @SerializedName("company_profile") val companyProfile: CompanyProfileDto? = null,
    @SerializedName("share_structure") val shareStructure: ShareStructureDto? = null,
    @SerializedName("valuation") val valuation: ValuationMetricsDto? = null,
    @SerializedName("profitability") val profitability: ProfitabilityMetricsDto? = null,
    @SerializedName("growth") val growth: GrowthMetricsDto? = null,
    @SerializedName("financials") val financials: FinancialStatementsDto? = null,
    @SerializedName("cash_flow") val cashFlow: CashFlowStatementsDto? = null,
    @SerializedName("equity_profile") val equityProfile: EquityProfileDto? = null,
    @SerializedName("ratios") val ratios: FinancialRatiosDto? = null,
    @SerializedName("financial_ratios") val financialRatios: FinancialRatiosDto? = null,
    @SerializedName("trading_limits") val tradingLimits: TradingLimitsDto? = null,
    @SerializedName("dividend_history") val dividendHistory: List<DividendHistoryItemDto>? = null,
    @SerializedName("dividends") val dividends: DividendsSummaryDto? = null,
    @SerializedName("financial_reports") val financialReports: List<FinancialReportItemDto>? = null,
    @SerializedName("announcements") val announcements: List<AnnouncementItemDto>? = null,
    @SerializedName("metrics") val metrics: List<FundamentalMetricDto>? = null,
    @SerializedName("extras") val extras: FundamentalsExtrasDto? = null,
    @SerializedName("sector_overview") val sectorOverview: SectorOverviewDto? = null
)

data class FundamentalsSourceDto(
    @SerializedName("primary") val primary: String? = null,
    @SerializedName("psx_official_url") val psxOfficialUrl: String? = null,
    @SerializedName("last_updated") val lastUpdated: String? = null
)

data class ShareStructureDto(
    @SerializedName("market_cap_pkr") val marketCapPkr: Double? = null,
    @SerializedName("market_cap_pkr_m") val marketCapPkrM: Double? = null,
    @SerializedName("total_shares") val totalShares: Long? = null,
    @SerializedName("shares_outstanding") val sharesOutstanding: Long? = null,
    @SerializedName("free_float_shares") val freeFloatShares: Long? = null,
    @SerializedName("free_float_pct") val freeFloatPct: Double? = null,
    @SerializedName("paid_up_capital_pkr") val paidUpCapitalPkr: Double? = null,
    @SerializedName("face_value_per_share") val faceValuePerShare: Double? = null,
    @SerializedName("book_value_per_share") val bookValuePerShare: Double? = null
)

data class ValuationMetricsDto(
    @SerializedName("share_price") val sharePrice: Double? = null,
    @SerializedName("pe_ratio") val peRatio: Double? = null,
    @SerializedName("price_to_book") val priceToBook: Double? = null,
    @SerializedName("peg_ratio") val pegRatio: Double? = null,
    @SerializedName("price_to_sales") val priceToSales: Double? = null,
    @SerializedName("ev_to_ebitda") val evToEbitda: Double? = null,
    @SerializedName("enterprise_value_pkr") val enterpriseValuePkr: Double? = null,
    @SerializedName("earnings_yield_pct") val earningsYieldPct: Double? = null,
    @SerializedName("dividend_yield_pct") val dividendYieldPct: Double? = null,
    @SerializedName("book_value_per_share") val bookValuePerShare: Double? = null
)

data class ProfitabilityMetricsDto(
    @SerializedName("revenue") val revenue: Double? = null,
    @SerializedName("gross_profit") val grossProfit: Double? = null,
    @SerializedName("operating_profit") val operatingProfit: Double? = null,
    @SerializedName("profit_before_tax") val profitBeforeTax: Double? = null,
    @SerializedName("profit_after_tax") val profitAfterTax: Double? = null,
    @SerializedName("eps") val eps: Double? = null,
    @SerializedName("gross_profit_margin_pct") val grossProfitMarginPct: Double? = null,
    @SerializedName("operating_margin_pct") val operatingMarginPct: Double? = null,
    @SerializedName("operating_profit_margin_pct") val operatingProfitMarginPct: Double? = null,
    @SerializedName("net_profit_margin_pct") val netProfitMarginPct: Double? = null,
    @SerializedName("roe_pct") val roePct: Double? = null,
    @SerializedName("roa_pct") val roaPct: Double? = null,
    @SerializedName("roic_pct") val roicPct: Double? = null,
    @SerializedName("ebitda_margin_pct") val ebitdaMarginPct: Double? = null
)

data class GrowthMetricsDto(
    @SerializedName("revenue_growth_yoy_pct") val revenueGrowthYoyPct: Double? = null,
    @SerializedName("profit_growth_yoy_pct") val profitGrowthYoyPct: Double? = null,
    @SerializedName("eps_growth_yoy_pct") val epsGrowthYoyPct: Double? = null,
    @SerializedName("revenue_cagr_3y_pct") val revenueCagr3yPct: Double? = null,
    @SerializedName("profit_cagr_3y_pct") val profitCagr3yPct: Double? = null,
    @SerializedName("eps_cagr_3y_pct") val epsCagr3yPct: Double? = null,
    @SerializedName("quarterly_revenue_growth_yoy_pct") val quarterlyRevenueGrowthYoyPct: Double? = null,
    @SerializedName("quarterly_profit_growth_yoy_pct") val quarterlyProfitGrowthYoyPct: Double? = null
)

data class FinancialStatementsDto(
    @SerializedName("unit") val unit: String? = null,
    @SerializedName("annual") val annual: List<FinancialStatementItemDto>? = null,
    @SerializedName("quarterly") val quarterly: List<FinancialStatementItemDto>? = null
)

data class FinancialStatementItemDto(
    @SerializedName("period") val period: String? = null,
    @SerializedName("revenue") val revenue: Double? = null,
    @SerializedName("sales") val sales: Double? = null,
    @SerializedName("profit_after_tax") val profitAfterTax: Double? = null,
    @SerializedName("net_profit") val netProfit: Double? = null,
    @SerializedName("eps") val eps: Double? = null
)

data class CashFlowStatementsDto(
    @SerializedName("annual") val annual: List<CashFlowItemDto>? = null,
    @SerializedName("quarterly") val quarterly: List<CashFlowItemDto>? = null
)

data class CashFlowItemDto(
    @SerializedName("period") val period: String? = null,
    @SerializedName("free_cash_flow") val freeCashFlow: Double? = null
)

data class DividendsSummaryDto(
    @SerializedName("current_dividend_per_share") val currentDividendPerShare: Double? = null,
    @SerializedName("dividend_yield_pct") val dividendYieldPct: Double? = null,
    @SerializedName("payout_ratio_pct") val payoutRatioPct: Double? = null,
    @SerializedName("dividend_growth_pct") val dividendGrowthPct: Double? = null,
    @SerializedName("dividend_cover") val dividendCover: Double? = null,
    @SerializedName("history") val history: List<DividendHistoryItemDto>? = null
)

data class CompanyProfileDto(
    @SerializedName("name") val name: String? = null,
    @SerializedName("sector") val sector: String? = null,
    @SerializedName("business_description") val businessDescription: String? = null,
    @SerializedName("ceo") val ceo: String? = null,
    @SerializedName("chairperson") val chairperson: String? = null,
    @SerializedName("company_secretary") val companySecretary: String? = null,
    @SerializedName("website") val website: String? = null,
    @SerializedName("address") val address: String? = null
)

data class EquityProfileDto(
    @SerializedName("market_cap_pkr") val marketCapPkr: Double? = null,
    @SerializedName("market_cap_pkr_m") val marketCapPkrM: Double? = null,
    @SerializedName("total_shares") val totalShares: Long? = null,
    @SerializedName("free_float_shares") val freeFloatShares: Long? = null,
    @SerializedName("free_float_pct") val freeFloatPct: Double? = null
)

data class FinancialRatiosDto(
    @SerializedName("pe_ratio") val peRatio: Double? = null,
    @SerializedName("price_to_book") val priceToBook: Double? = null,
    @SerializedName("debt_to_equity") val debtToEquity: Double? = null,
    @SerializedName("current_ratio") val currentRatio: Double? = null,
    @SerializedName("quick_ratio") val quickRatio: Double? = null,
    @SerializedName("interest_coverage_ratio") val interestCoverageRatio: Double? = null,
    @SerializedName("interest_coverage") val interestCoverage: Double? = null,
    @SerializedName("peg_ratio") val pegRatio: Double? = null,
    @SerializedName("eps") val eps: Double? = null,
    @SerializedName("eps_growth_pct") val epsGrowthPct: Double? = null,
    @SerializedName("net_profit_margin_pct") val netProfitMarginPct: Double? = null,
    @SerializedName("gross_profit_margin_pct") val grossProfitMarginPct: Double? = null,
    @SerializedName("dividend_yield_pct") val dividendYieldPct: Double? = null
)

data class TradingLimitsDto(
    @SerializedName("year_high") val yearHigh: Double? = null,
    @SerializedName("year_low") val yearLow: Double? = null,
    @SerializedName("circuit_breaker_lower") val circuitBreakerLower: Double? = null,
    @SerializedName("circuit_breaker_upper") val circuitBreakerUpper: Double? = null,
    @SerializedName("year_change_pct") val yearChangePct: Double? = null,
    @SerializedName("ytd_change_pct") val ytdChangePct: Double? = null
)

data class DividendHistoryItemDto(
    @SerializedName("ex_date") val exDate: String? = null,
    @SerializedName("cash_amount") val cashAmount: String? = null,
    @SerializedName("record_date") val recordDate: String? = null,
    @SerializedName("pay_date") val payDate: String? = null,
    @SerializedName("announcement_date") val announcementDate: String? = null,
    @SerializedName("financial_year") val financialYear: String? = null,
    @SerializedName("type") val type: String? = null,
    @SerializedName("amount_per_share") val amountPerShare: Double? = null,
    @SerializedName("dividend_pct") val dividendPct: Double? = null
)

data class FinancialReportItemDto(
    @SerializedName("report_type") val reportType: String? = null,
    @SerializedName("period_ended") val periodEnded: String? = null,
    @SerializedName("posting_date") val postingDate: String? = null,
    @SerializedName("url") val url: String? = null
)

data class AnnouncementItemDto(
    @SerializedName("date") val date: String? = null,
    @SerializedName("title") val title: String? = null,
    @SerializedName("category") val category: String? = null,
    @SerializedName("description") val description: String? = null
)

data class FundamentalMetricDto(
    @SerializedName("key") val key: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("value") val value: JsonElement? = null,
    @SerializedName("note") val note: String? = null,
    @SerializedName("category") val category: String? = null,
    @SerializedName("trend") val trend: String? = null
) {
    fun getValueAsString(): String? = when {
        value == null || value.isJsonNull -> null
        value.isJsonPrimitive -> value.asString
        else -> value.toString()
    }

    fun getValueAsDouble(): Double? = when {
        value == null || value.isJsonNull -> null
        value.isJsonPrimitive -> value.asString.toDoubleOrNull()
        else -> null
    }
}

data class FundamentalsExtrasDto(
    @SerializedName("book_value_per_share") val bookValuePerShare: Double? = null,
    @SerializedName("price_to_book") val priceToBook: Double? = null,
    @SerializedName("debt_to_equity") val debtToEquity: Double? = null,
    @SerializedName("current_ratio") val currentRatio: Double? = null,
    @SerializedName("quick_ratio") val quickRatio: Double? = null,
    @SerializedName("roe_pct") val roePct: Double? = null,
    @SerializedName("roa_pct") val roaPct: Double? = null,
    @SerializedName("interest_coverage") val interestCoverage: Double? = null,
    @SerializedName("year_change_pct") val yearChangePct: Double? = null,
    @SerializedName("ytd_change_pct") val ytdChangePct: Double? = null,
    @SerializedName("gross_profit_margin_pct") val grossProfitMarginPct: Double? = null,
    @SerializedName("net_profit_margin_pct") val netProfitMarginPct: Double? = null,
    @SerializedName("eps_growth_pct") val epsGrowthPct: Double? = null
)

data class SectorOverviewDto(
    @SerializedName("sector") val sector: String? = null,
    @SerializedName("companies_count") val companiesCount: Int? = null,
    @SerializedName("avg_change_pct") val avgChangePct: Double? = null,
    @SerializedName("advancing") val advancing: Int? = null,
    @SerializedName("declining") val declining: Int? = null,
    @SerializedName("unchanged") val unchanged: Int? = null,
    @SerializedName("stock_rank") val stockRank: Int? = null
)
