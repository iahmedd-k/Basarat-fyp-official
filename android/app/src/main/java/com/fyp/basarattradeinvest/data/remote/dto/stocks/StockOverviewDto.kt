package com.fyp.basarattradeinvest.data.remote.dto.stocks

import com.google.gson.annotations.SerializedName

data class StockOverviewDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("sector") val sector: String? = null,
    @SerializedName("current_price") val currentPrice: Double? = null,
    @SerializedName("ltp") val ltp: Double? = null,
    @SerializedName("ldcp") val ldcp: Double? = null,
    @SerializedName("change") val change: Double? = null,
    @SerializedName("change_pct") val changePct: Double? = null,
    @SerializedName("day_range") val dayRange: DayRangeDto? = null,
    @SerializedName("volume") val volume: Long? = null,
    @SerializedName("market_cap_m") val marketCapM: Double? = null,
    @SerializedName("market_cap") val marketCap: Double? = null,
    @SerializedName("pe_ratio") val peRatio: Double? = null,
    @SerializedName("year_change_pct") val yearChangePct: Double? = null,
    @SerializedName("ytd_change_pct") val ytdChangePct: Double? = null
)

data class DayRangeDto(
    @SerializedName("low") val low: Double? = null,
    @SerializedName("high") val high: Double? = null
)
