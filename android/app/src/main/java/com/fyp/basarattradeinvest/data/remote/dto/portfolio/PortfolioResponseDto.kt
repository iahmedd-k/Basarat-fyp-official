package com.fyp.basarattradeinvest.data.remote.dto.portfolio

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger Schema for PortfolioResponse
 * GET /api/v1/portfolio
 */
data class PortfolioResponseDto(
    @SerializedName("summary")
    val summary: PortfolioSummaryDto,
    @SerializedName("holdings")
    val holdings: List<HoldingItemDto>,
    @SerializedName("updated_at")
    val updatedAt: String
)

data class PortfolioSummaryDto(
    @SerializedName("total_invested")
    val totalInvested: String,
    @SerializedName("current_value")
    val currentValue: String,
    @SerializedName("total_pnl")
    val totalPnl: String,
    @SerializedName("total_pnl_percent")
    val totalPnlPercent: Double,
    @SerializedName("today_pnl")
    val todayPnl: String
)

data class HoldingItemDto(
    @SerializedName("symbol")
    val symbol: String,
    @SerializedName("quantity")
    val quantity: String,
    @SerializedName("average_cost")
    val averageCost: String,
    @SerializedName("company_name")
    val companyName: String? = null,
    @SerializedName("sector")
    val sector: String? = null,
    @SerializedName("current_price")
    val currentPrice: String? = null,
    @SerializedName("market_value")
    val marketValue: String? = null,
    @SerializedName("unrealized_pnl")
    val unrealizedPnl: String? = null,
    @SerializedName("unrealized_pnl_percent")
    val unrealizedPnlPercent: Double? = null,
    @SerializedName("portfolio_weight")
    val portfolioWeight: Double? = null,
    @SerializedName("price_updated_at")
    val priceUpdatedAt: String? = null,
    @SerializedName("price_status")
    val priceStatus: String? = "AVAILABLE"
)
