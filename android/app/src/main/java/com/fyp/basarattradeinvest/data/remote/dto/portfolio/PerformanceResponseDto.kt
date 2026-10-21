package com.fyp.basarattradeinvest.data.remote.dto.portfolio

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger Schema for PerformanceResponse
 * GET /api/v1/portfolio/performance
 */
data class PerformanceResponseDto(
    @SerializedName("period")
    val period: String,
    @SerializedName("data")
    val data: List<PerformancePointDto>
)

data class PerformancePointDto(
    @SerializedName("date")
    val date: String,
    @SerializedName("value")
    val value: String
)
