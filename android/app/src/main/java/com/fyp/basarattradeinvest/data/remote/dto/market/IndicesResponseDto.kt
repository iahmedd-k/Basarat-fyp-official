package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for GET /api/v1/market/indices
 */
data class IndicesResponseDto(
    @SerializedName("indices")
    val indices: List<IndexItemDto>?
)

data class IndexItemDto(
    @SerializedName("index")
    val index: String?,
    @SerializedName("code")
    val code: String?,
    @SerializedName("current")
    val current: Double?,
    @SerializedName("change")
    val change: Double?,
    @SerializedName("change_pct")
    val changePct: Double?,
    @SerializedName("high")
    val high: Double?,
    @SerializedName("low")
    val low: Double?
)
