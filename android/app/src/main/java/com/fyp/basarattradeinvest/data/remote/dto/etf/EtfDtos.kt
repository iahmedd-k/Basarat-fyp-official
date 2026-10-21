package com.fyp.basarattradeinvest.data.remote.dto.etf

import com.google.gson.annotations.SerializedName

data class EtfQuoteDto(
    @SerializedName("current_price") val currentPrice: Double?,
    @SerializedName("change") val change: Double?,
    @SerializedName("change_percent") val changePercent: Double?,
    @SerializedName("open_price") val openPrice: Double?,
    @SerializedName("high_price") val highPrice: Double?,
    @SerializedName("low_price") val lowPrice: Double?,
    @SerializedName("close_price") val closePrice: Double?,
    @SerializedName("volume") val volume: Long?,
    @SerializedName("bid_price") val bidPrice: Double?,
    @SerializedName("ask_price") val askPrice: Double?,
    @SerializedName("data_as_of") val dataAsOf: String?,
    @SerializedName("quote_source") val quoteSource: String?
)

data class EtfItemDto(
    @SerializedName("id") val id: String?,
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("name") val name: String?,
    @SerializedName("fund_manager") val fundManager: String?,
    @SerializedName("category") val category: String?,
    @SerializedName("benchmark_index") val benchmarkIndex: String?,
    @SerializedName("is_shariah_compliant") val isShariahCompliant: Boolean?,
    @SerializedName("expense_ratio") val expenseRatio: Double?,
    @SerializedName("inception_date") val inceptionDate: String?,
    @SerializedName("total_assets_pkr") val totalAssetsPkr: Double?,
    @SerializedName("description") val description: String?,
    @SerializedName("is_active") val isActive: Boolean?,
    @SerializedName("quote") val quote: EtfQuoteDto?,
    @SerializedName("current_price") val currentPrice: Double?,
    @SerializedName("change") val change: Double?,
    @SerializedName("change_percent") val changePercent: Double?,
    @SerializedName("volume") val volume: Long?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("updated_at") val updatedAt: String?
)

data class EtfsResponseDto(
    @SerializedName("total") val total: Int?,
    @SerializedName("shariah_count") val shariahCount: Int?,
    @SerializedName("conventional_count") val conventionalCount: Int?,
    @SerializedName("etfs") val etfs: List<EtfItemDto>?
)

data class EtfHistoryEntryDto(
    @SerializedName("date") val date: String?,
    @SerializedName("open") val open: Double?,
    @SerializedName("high") val high: Double?,
    @SerializedName("low") val low: Double?,
    @SerializedName("close") val close: Double?,
    @SerializedName("volume") val volume: Long?
)

data class EtfHistoryResponseDto(
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("timeframe") val timeframe: String?,
    @SerializedName("count") val count: Int?,
    @SerializedName("history") val history: List<EtfHistoryEntryDto>?
)

data class EtfReturnsDto(
    @SerializedName("1D") val oneDay: Double?,
    @SerializedName("1W") val oneWeek: Double?,
    @SerializedName("1M") val oneMonth: Double?,
    @SerializedName("3M") val threeMonths: Double?,
    @SerializedName("1Y") val oneYear: Double?,
    @SerializedName("YTD") val ytd: Double?
)

data class EtfPerformanceDto(
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("name") val name: String?,
    @SerializedName("benchmark_index") val benchmarkIndex: String?,
    @SerializedName("returns") val returns: EtfReturnsDto?,
    @SerializedName("benchmark_returns") val benchmarkReturns: EtfReturnsDto?,
    @SerializedName("tracking_difference_1m") val trackingDifference1m: Double?,
    @SerializedName("volatility_annualized") val volatilityAnnualized: Double?
)
