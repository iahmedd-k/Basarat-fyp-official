package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

data class MarketStockDto(
    @SerializedName("rank") val rank: Int?,
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("company_name") val companyName: String?,
    @SerializedName("sector_code") val sectorCode: String?,
    @SerializedName("price") val price: Double?,
    @SerializedName("change") val change: Double?,
    @SerializedName("change_percent") val changePercent: Double?,
    @SerializedName("volume") val volume: String?,
    @SerializedName("is_shariah") val isShariah: Boolean?
)
