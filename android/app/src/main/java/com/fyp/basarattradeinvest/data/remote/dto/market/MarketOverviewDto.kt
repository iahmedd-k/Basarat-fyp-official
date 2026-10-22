package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

data class MarketOverviewDto(
    @SerializedName("traded_value") val tradedValue: String?,
    @SerializedName("traded_volume") val tradedVolume: String?,
    @SerializedName("total_trades") val totalTrades: String?,
    @SerializedName("up_count") val upCount: Int?,
    @SerializedName("unchanged_count") val unchangedCount: Int?,
    @SerializedName("down_count") val downCount: Int?,
    @SerializedName("total_stocks") val totalStocks: Int?
)
