package com.fyp.basarattradeinvest.data.remote.dto.alerts

import com.google.gson.annotations.SerializedName

/** Nested rule returned as part of the quick-alert response. */
data class AlertRuleResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("user_id")
    val userId: String,

    @SerializedName("stock_id")
    val stockId: String? = null,

    @SerializedName("symbol")
    val symbol: String? = null,

    @SerializedName("stock_name")
    val stockName: String? = null,

    @SerializedName("condition")
    val condition: String,

    @SerializedName("threshold")
    val threshold: Double,

    @SerializedName("is_active")
    val isActive: Boolean,

    @SerializedName("created_at")
    val createdAt: String
)

/**
 * OpenAPI QuickAlertRuleCreate. The backend applies its documented defaults for
 * percent_threshold (3.0) and direction (both) when those optional fields are omitted.
 */
data class QuickAlertRuleCreateDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("stock_name") val stockName: String? = null,
    @SerializedName("stock_id") val stockId: String? = null,
    @SerializedName("percent_threshold") val percentThreshold: Double? = null,
    @SerializedName("direction") val direction: String? = null
)

/** Exact OpenAPI QuickAlertRuleResponse for POST /api/v1/alerts/quick-rule. */
data class QuickAlertRuleResponseDto(
    @SerializedName("symbol") val symbol: String,
    @SerializedName("stock_name") val stockName: String? = null,
    @SerializedName("stock_id") val stockId: String,
    @SerializedName("base_price") val basePrice: Double,
    @SerializedName("percent_threshold") val percentThreshold: Double,
    @SerializedName("direction") val direction: String,
    @SerializedName("rules") val rules: List<AlertRuleResponseDto>,
    @SerializedName("message") val message: String
)

/**
 * Exact OpenAPI schema for AlertResponse
 * Returned by GET /api/v1/alerts
 */
data class AlertResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("user_id")
    val userId: String,

    @SerializedName("rule_id")
    val ruleId: String? = null,

    @SerializedName("title")
    val title: String,

    @SerializedName("message")
    val message: String? = null,

    @SerializedName("is_read")
    val isRead: Boolean,

    @SerializedName("created_at")
    val createdAt: String
)
