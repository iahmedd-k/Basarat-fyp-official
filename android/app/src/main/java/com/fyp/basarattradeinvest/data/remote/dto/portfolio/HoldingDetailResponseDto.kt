package com.fyp.basarattradeinvest.data.remote.dto.portfolio

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger Schema for HoldingDetailResponse
 * GET /api/v1/portfolio/holdings/{symbol}
 */
data class HoldingDetailResponseDto(
    @SerializedName("symbol")
    val symbol: String,
    @SerializedName("company_name")
    val companyName: String? = null,
    @SerializedName("sector")
    val sector: String? = null,
    @SerializedName("quantity")
    val quantity: String,
    @SerializedName("average_cost")
    val averageCost: String,
    @SerializedName("current_price")
    val currentPrice: String? = null,
    @SerializedName("invested_value")
    val investedValue: String,
    @SerializedName("market_value")
    val marketValue: String? = null,
    @SerializedName("unrealized_pnl")
    val unrealizedPnl: String? = null,
    @SerializedName("unrealized_pnl_percent")
    val unrealizedPnlPercent: Double? = null,
    @SerializedName("realized_pnl")
    val realizedPnl: String,
    @SerializedName("portfolio_weight")
    val portfolioWeight: Double? = null,
    @SerializedName("transactions")
    val transactions: List<TransactionResponseDto> = emptyList(),
    @SerializedName("price_updated_at")
    val priceUpdatedAt: String? = null,
    @SerializedName("price_status")
    val priceStatus: String? = "AVAILABLE"
)
