package com.fyp.basarattradeinvest.data.remote.dto.portfolio

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger Schema for AllocationResponse
 * GET /api/v1/portfolio/allocation
 */
data class AllocationResponseDto(
    @SerializedName("by_stock")
    val byStock: List<AllocationByStockDto>,
    @SerializedName("by_sector")
    val bySector: List<AllocationBySectorDto>
)

data class AllocationByStockDto(
    @SerializedName("symbol")
    val symbol: String,
    @SerializedName("market_value")
    val marketValue: String,
    @SerializedName("percentage")
    val percentage: Double
)

data class AllocationBySectorDto(
    @SerializedName("sector")
    val sector: String,
    @SerializedName("market_value")
    val marketValue: String,
    @SerializedName("percentage")
    val percentage: Double
)
