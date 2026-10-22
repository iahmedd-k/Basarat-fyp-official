package com.fyp.basarattradeinvest.domain.model.stock

/**
 * Domain model representing historical forecast accuracy and previous predictions
 */
data class ForecastHistory(
    val symbol: String,
    val horizon: String,
    val count: Int,
    val accuracy: Double?,
    val history: List<ForecastHistoryRecord>
)

data class ForecastHistoryRecord(
    val predictedAt: String,
    val predictedDirection: ForecastDirection,
    val probabilities: Map<String, Double>,
    val confidence: Double,
    val targetDate: String,
    val actualOutcome: ForecastActualOutcome?
)

data class ForecastActualOutcome(
    val direction: String,
    val wasCorrect: Boolean?
)
