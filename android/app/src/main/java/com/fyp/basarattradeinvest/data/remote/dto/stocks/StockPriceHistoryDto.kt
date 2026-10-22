package com.fyp.basarattradeinvest.data.remote.dto.stocks

import com.google.gson.annotations.SerializedName

data class PriceHistoryResponseDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("range") val range: String? = null,
    @SerializedName("bars") val bars: List<PriceBarDto>? = null
)

data class PriceBarDto(
    @SerializedName("date") val date: String? = null,
    @SerializedName("open") val open: Double = 0.0,
    @SerializedName("high") val high: Double = 0.0,
    @SerializedName("low") val low: Double = 0.0,
    @SerializedName("close") val close: Double = 0.0,
    @SerializedName("volume") val volume: Long = 0L
)
