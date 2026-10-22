package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

data class MarketIndexDto(
    @SerializedName("id") val id: String?,
    @SerializedName("name") val name: String?,
    @SerializedName("current_points") val currentPoints: Double?,
    @SerializedName("change_points") val changePoints: Double?,
    @SerializedName("change_percent") val changePercent: Double?,
    @SerializedName("intraday_points") val intradayPoints: List<Float>?
)
