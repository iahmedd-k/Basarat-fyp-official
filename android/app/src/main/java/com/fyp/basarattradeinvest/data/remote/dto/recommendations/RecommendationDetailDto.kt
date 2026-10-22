package com.fyp.basarattradeinvest.data.remote.dto.recommendations

import com.google.gson.annotations.SerializedName

data class RecommendationDetailResponseDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("sector") val sector: String? = null,
    @SerializedName("signal") val signal: String? = null,
    @SerializedName("confidence") val confidence: Double? = null,
    @SerializedName("composite_score") val compositeScore: Double? = null,
    @SerializedName("signals") val signals: Map<String, Double>? = emptyMap(),
    @SerializedName("target_price") val targetPrice: Double? = null,
    @SerializedName("stop_loss") val stopLoss: Double? = null,
    @SerializedName("expected_range") val expectedRange: Map<String, Any>? = null,
    @SerializedName("current_price") val currentPrice: Double? = null,
    @SerializedName("atr_14") val atr14: Double? = null,
    @SerializedName("reasoning") val reasoning: Map<String, Any>? = emptyMap(),
    @SerializedName("weights") val weights: Map<String, Double>? = emptyMap(),
    @SerializedName("generated_at") val generatedAt: String? = null,
    @SerializedName("risk_profile") val riskProfile: String? = null,
    @SerializedName("decision") val decision: RecommendationDecisionNestedDto? = null,
    @SerializedName("market_data") val marketData: RecommendationMarketDataNestedDto? = null,
    @SerializedName("risk") val risk: TargetStopRiskDto? = null,
    @SerializedName("components") val components: Map<String, RecommendationComponentDto>? = null,
    @SerializedName("summary") val summary: String? = null
) {
    fun getResolvedSignal(): String = signal ?: decision?.signal ?: "HOLD"
    fun getResolvedConfidence(): Double = confidence ?: decision?.confidence ?: 0.5
    fun getResolvedCompositeScore(): Double = compositeScore ?: decision?.compositeScore ?: 0.0
    fun getResolvedCurrentPrice(): Double? = currentPrice ?: marketData?.currentPrice
    fun getResolvedTargetPrice(): Double? = targetPrice ?: risk?.targetPrice
    fun getResolvedStopLoss(): Double? = stopLoss ?: risk?.stopLoss
    fun getResolvedAtr14(): Double? = atr14 ?: risk?.atr14
    fun getResolvedExpectedRange(): Map<String, Any>? = expectedRange ?: risk?.expectedRange
}

data class RecommendationDecisionNestedDto(
    @SerializedName("signal") val signal: String? = null,
    @SerializedName("composite_score") val compositeScore: Double? = null,
    @SerializedName("confidence") val confidence: Double? = null,
    @SerializedName("confidence_type") val confidenceType: String? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("horizon") val horizon: String? = null,
    @SerializedName("reason") val reason: String? = null,
    @SerializedName("suppressed") val suppressed: Boolean? = null,
    @SerializedName("suppression_reason") val suppressionReason: String? = null
)

data class RecommendationMarketDataNestedDto(
    @SerializedName("current_price") val currentPrice: Double? = null,
    @SerializedName("freshness") val freshness: String? = null,
    @SerializedName("analysis_freshness") val analysisFreshness: String? = null,
    @SerializedName("analysis_age_trading_days") val analysisAgeTradingDays: Int? = null
)
