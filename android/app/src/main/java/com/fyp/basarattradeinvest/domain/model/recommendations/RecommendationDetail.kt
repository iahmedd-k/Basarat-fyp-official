package com.fyp.basarattradeinvest.domain.model.recommendations

data class RecommendationDetail(
    val symbol: String,
    val signal: RecommendationSignal,
    val confidence: Double,
    val compositeScore: Double,
    val individualSignals: Map<String, Double>,
    val targetPrice: Double?,
    val stopLoss: Double?,
    val expectedRange: ExpectedPriceRange?,
    val currentPrice: Double?,
    val atr14: Double?,
    val reasoning: Map<String, Map<String, String>>,
    val weights: Map<String, Double>,
    val name: String? = null,
    val sector: String? = null,
    val horizon: String? = null,
    val decisionReason: String? = null,
    val suppressionReason: String? = null,
    val isSuppressed: Boolean = false,
    val components: List<RecommendationComponent> = emptyList(),
    val riskProfile: String? = null
)

data class RecommendationComponent(
    val key: String,
    val score: Double?,
    val status: String?,
    val configuredWeight: Double?,
    val effectiveWeight: Double?,
    val availabilityReason: String?,
    val details: Map<String, String>
)

data class ExpectedPriceRange(
    val low: Double,
    val high: Double,
    val method: String
)
