package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for GET /api/v1/market/sentiment-overview
 */
data class SentimentOverviewDto(
    @SerializedName("market_mood")
    val marketMood: String?,
    @SerializedName("advancing")
    val advancing: Int?,
    @SerializedName("declining")
    val declining: Int?,
    @SerializedName("unchanged")
    val unchanged: Int?,
    @SerializedName("advance_decline_ratio")
    val advanceDeclineRatio: Double?,
    @SerializedName("gainers_pct")
    val gainersPct: Double?,
    @SerializedName("losers_pct")
    val losersPct: Double?,
    @SerializedName("sector_performance")
    val sectorPerformance: List<SectorPerformanceItemDto>?,
    @SerializedName("top_movers")
    val topMovers: List<MarketQuoteItemDto>?
)

data class SectorPerformanceItemDto(
    @SerializedName("sector")
    val sector: String?,
    @SerializedName("avg_change_pct")
    val avgChangePct: Double?,
    @SerializedName("companies")
    val companies: Int?
)
