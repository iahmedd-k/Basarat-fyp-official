package com.fyp.basarattradeinvest.data.remote.dto.portfolio

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger Schema for TransactionResponse & TransactionListResponse
 * GET /api/v1/portfolio/transactions
 * GET /api/v1/portfolio/transactions/{transaction_id}
 */
data class TransactionListResponseDto(
    @SerializedName("items")
    val items: List<TransactionResponseDto>,
    @SerializedName("total")
    val total: Int,
    @SerializedName("page")
    val page: Int,
    @SerializedName("limit")
    val limit: Int
)

data class TransactionResponseDto(
    @SerializedName("id")
    val id: String,
    @SerializedName("symbol")
    val symbol: String,
    @SerializedName("transaction_type")
    val transactionType: String,
    @SerializedName("quantity")
    val quantity: String,
    @SerializedName("price")
    val price: String,
    @SerializedName("fee")
    val fee: String,
    @SerializedName("transaction_date")
    val transactionDate: String,
    @SerializedName("created_at")
    val createdAt: String,
    @SerializedName("updated_at")
    val updatedAt: String
)

data class TransactionCreateDto(
    @SerializedName("symbol")
    val symbol: String,
    @SerializedName("transaction_type")
    val transactionType: String,
    @SerializedName("quantity")
    val quantity: Any,
    @SerializedName("price")
    val price: Any,
    @SerializedName("fee")
    val fee: Any = "0",
    @SerializedName("transaction_date")
    val transactionDate: String
)

data class TransactionUpdateDto(
    @SerializedName("quantity")
    val quantity: Any? = null,
    @SerializedName("price")
    val price: Any? = null,
    @SerializedName("fee")
    val fee: Any? = null,
    @SerializedName("transaction_date")
    val transactionDate: String? = null
)
