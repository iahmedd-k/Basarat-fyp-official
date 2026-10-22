package com.fyp.basarattradeinvest.domain.model.recommendations

data class StockRecommendation(
    val symbol: String,
    val signal: RecommendationSignal,
    val confidence: Double,
    val compositeScore: Double,
    val targetPrice: Double?,
    val stopLoss: Double?,
    val summary: String,
    val currentPrice: Double? = null
)

enum class RecommendationSignal(val label: String) {
    BUY("BUY"),
    HOLD("HOLD"),
    SELL("SELL");

    companion object {
        fun fromString(value: String?): RecommendationSignal {
            return when (value?.trim()?.uppercase()) {
                "BUY" -> BUY
                "SELL" -> SELL
                else -> HOLD
            }
        }
    }
}
