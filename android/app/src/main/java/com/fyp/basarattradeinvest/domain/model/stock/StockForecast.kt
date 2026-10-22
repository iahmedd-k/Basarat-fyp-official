package com.fyp.basarattradeinvest.domain.model.stock

/**
 * Domain model representing ML forecast output for a stock
 */
data class StockForecast(
    val symbol: String,
    val horizon: String,
    val direction: ForecastDirection,
    val confidence: Double,
    val currentPrice: Double?,
    val targetPrice: Double?,
    val targetDate: String,
    val asOfDate: String,
    val stopLoss: Double?,
    val upsidePct: Double?,
    val downsidePct: Double?,
    val riskRewardRatio: Double?,
    val signalRating: String?,
    val modelVersion: String?,
    val gateReason: String?,
    val probabilities: ForecastProbabilities?,
    val models: Map<String, ForecastModelDetail>,
    val marketContext: ForecastMarketContext?
)

enum class ForecastDirection(val label: String) {
    BULLISH("Bullish"),
    BEARISH("Bearish"),
    SIDEWAYS("Sideways");

    companion object {
        fun fromString(value: String): ForecastDirection {
            return when (value.lowercase().trim()) {
                "bullish" -> BULLISH
                "bearish" -> BEARISH
                "sideways" -> SIDEWAYS
                else -> SIDEWAYS
            }
        }
    }
}

data class ForecastProbabilities(
    val bullish: Double?,
    val bearish: Double?,
    val sideways: Double?
)

data class ForecastModelDetail(
    val direction: String,
    val bullishPct: Double?,
    val bearishPct: Double?,
    val sidewaysPct: Double?,
    val gapPp: Double?
)

data class ForecastMarketContext(
    val marketReturn5d: Double?,
    val marketReturn20d: Double?,
    val stockReturn20d: Double?,
    val stockRelativeReturn20d: Double?
)
