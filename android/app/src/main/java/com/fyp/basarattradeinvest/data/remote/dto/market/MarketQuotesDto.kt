package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for MarketQuoteItem, GainersResponse, LosersResponse, VolumeSpikesResponse, SectorPerformanceResponse
 */
data class MarketQuoteItemDto(
    @SerializedName("symbol")
    val symbol: String?,
    @SerializedName("name")
    val name: String? = null,
    @SerializedName("sector")
    val sector: String?,
    @SerializedName("ldcp")
    val ldcp: Double?,
    @SerializedName("open")
    val open: Double?,
    @SerializedName("high")
    val high: Double?,
    @SerializedName("low")
    val low: Double?,
    @SerializedName("current")
    val current: Double?,
    @SerializedName("change")
    val change: Double?,
    @SerializedName("change_pct")
    val changePct: Double?,
    @SerializedName("volume")
    val volume: Long?,
    @SerializedName("market_cap_m")
    val marketCapM: Double? = null
)

data class GainersResponseDto(
    @SerializedName("gainers")
    val gainers: List<MarketQuoteItemDto>?
)

data class LosersResponseDto(
    @SerializedName("losers")
    val losers: List<MarketQuoteItemDto>?
)

data class VolumeSpikesResponseDto(
    @SerializedName("volume_spikes")
    val volumeSpikes: List<MarketQuoteItemDto>?
)

data class SectorPerformanceListResponseDto(
    @SerializedName("sectors")
    val sectors: List<SectorPerformanceDetailDto>?
)

data class SectorPerformanceDetailDto(
    @SerializedName("sector")
    val sector: String?,
    @SerializedName("avg_change_pct")
    val avgChangePct: Double?,
    @SerializedName("companies")
    val companies: Int?,
    @SerializedName("advancing")
    val advancing: Int? = null,
    @SerializedName("declining")
    val declining: Int? = null,
    @SerializedName("unchanged")
    val unchanged: Int? = null,
    @SerializedName("total_volume")
    val totalVolume: Long? = null,
    @SerializedName("market_cap_m")
    val marketCapM: Double? = null,
    @SerializedName("top_gainer_symbol")
    val topGainerSymbol: String? = null,
    @SerializedName("top_loser_symbol")
    val topLoserSymbol: String? = null
)
