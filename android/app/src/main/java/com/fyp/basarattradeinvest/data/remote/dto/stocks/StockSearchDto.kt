package com.fyp.basarattradeinvest.data.remote.dto.stocks

import com.google.gson.annotations.SerializedName

data class StockSearchResponseDto(
    @SerializedName("results") val results: List<StockSearchResultDto>? = null
)

data class StockSearchResultDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("sector") val sector: String? = null
)
