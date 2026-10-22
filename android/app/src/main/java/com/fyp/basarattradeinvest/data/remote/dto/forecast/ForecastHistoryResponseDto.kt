package com.fyp.basarattradeinvest.data.remote.dto.forecast

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger DTO for GET /api/v1/forecast/{symbol}/history
 */
data class ForecastHistoryResponseDto(
    @SerializedName("symbol")
    val symbol: String? = null,

    @SerializedName("horizon")
    val horizon: String? = null,

    @SerializedName("count")
    val count: Int = 0,

    @SerializedName("accuracy")
    val accuracy: Double? = null,

    @SerializedName("history")
    val history: List<ForecastHistoryItemDto>? = null
)

data class ForecastHistoryItemDto(
    @SerializedName("predicted_at")
    val predictedAt: String? = null,

    @SerializedName("predicted_direction")
    val predictedDirection: String? = null,

    @SerializedName("probabilities")
    val probabilities: Map<String, Double>? = null,

    @SerializedName("confidence")
    val confidence: Double = 0.0,

    @SerializedName("target_date")
    val targetDate: String? = null,

    @SerializedName("actual")
    val actual: ForecastActualOutcomeDto? = null
)

data class ForecastActualOutcomeDto(
    @SerializedName("direction")
    val direction: String? = null,

    @SerializedName("was_correct")
    val wasCorrect: Boolean? = null
)
