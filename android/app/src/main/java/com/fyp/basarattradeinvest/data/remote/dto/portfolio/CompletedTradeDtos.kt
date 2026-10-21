package com.fyp.basarattradeinvest.data.remote.dto.portfolio

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger Schema for CompletedTradeCreate and CompletedTradeResponse
 * POST /api/v1/portfolio/transactions/completed-trade
 */
data class CompletedTradeCreateDto(
    @SerializedName("symbol")
    val symbol: String,
    @SerializedName("quantity")
    val quantity: Any,
    @SerializedName("buy_price")
    val buyPrice: Any,
    @SerializedName("buy_date")
    val buyDate: String,
    @SerializedName("buy_fee")
    val buyFee: Any = "0",
    @SerializedName("sell_price")
    val sellPrice: Any,
    @SerializedName("sell_date")
    val sellDate: String,
    @SerializedName("sell_fee")
    val sellFee: Any = "0"
)

data class CompletedTradeResponseDto(
    @SerializedName("symbol")
    val symbol: String,
    @SerializedName("quantity")
    val quantity: String,
    @SerializedName("buy_price")
    val buyPrice: String,
    @SerializedName("buy_date")
    val buyDate: String,
    @SerializedName("buy_fee")
    val buyFee: String,
    @SerializedName("sell_price")
    val sellPrice: String,
    @SerializedName("sell_date")
    val sellDate: String,
    @SerializedName("sell_fee")
    val sellFee: String,
    @SerializedName("holding_period_days")
    val holdingPeriodDays: Int,
    @SerializedName("total_invested")
    val totalInvested: String,
    @SerializedName("total_proceeds")
    val totalProceeds: String,
    @SerializedName("realized_pnl")
    val realizedPnl: String,
    @SerializedName("realized_pnl_percent")
    val realizedPnlPercent: Double,
    @SerializedName("buy_transaction")
    val buyTransaction: TransactionResponseDto,
    @SerializedName("sell_transaction")
    val sellTransaction: TransactionResponseDto
)
