package com.fyp.basarattradeinvest.data.remote.dto.market

import com.google.gson.annotations.SerializedName

data class SectorPerformanceDto(
    @SerializedName("id")
    val id: String?,
    @SerializedName("sector_name")
    val sectorName: String?,
    @SerializedName("change_percent")
    val changePercent: Double?,
    @SerializedName("volume")
    val volume: String?
)
