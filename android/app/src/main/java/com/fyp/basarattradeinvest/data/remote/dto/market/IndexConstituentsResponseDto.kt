package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for GET /api/v1/market/indices/kse-100, kse-30, kmi-30
 */
data class IndexConstituentsResponseDto(
    @SerializedName("index")
    val index: String?,
    @SerializedName("code")
    val code: String?,
    @SerializedName("shariah_compliant")
    val shariahCompliant: Boolean?,
    @SerializedName("constituents")
    val constituents: List<ConstituentItemDto>?
)

data class ConstituentItemDto(
    @SerializedName("symbol")
    val symbol: String?,
    @SerializedName("name")
    val name: String?,
    @SerializedName("ldcp")
    val ldcp: Double?,
    @SerializedName("current")
    val current: Double?,
    @SerializedName("change")
    val change: Double?,
    @SerializedName("change_pct")
    val changePct: Double?,
    @SerializedName("weight_pct")
    val weightPct: Double?,
    @SerializedName("index_points")
    val indexPoints: Double?,
    @SerializedName("volume")
    val volume: Long?,
    @SerializedName("freefloat_m")
    val freeFloatM: Double?,
    @SerializedName("market_cap_m")
    val marketCapM: Double?
)
