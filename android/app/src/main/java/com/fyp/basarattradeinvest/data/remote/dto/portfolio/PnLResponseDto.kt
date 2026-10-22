package com.fyp.basarattradeinvest.data.remote.dto.portfolio

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger Schema for PnLResponse
 * GET /api/v1/portfolio/pnl
 */
data class PnLResponseDto(
    @SerializedName("realized_pnl")
    val realizedPnl: String,
    @SerializedName("unrealized_pnl")
    val unrealizedPnl: String,
    @SerializedName("total_pnl")
    val totalPnl: String,
    @SerializedName("total_pnl_percent")
    val totalPnlPercent: Double,
    @SerializedName("today_pnl")
    val todayPnl: String
)
