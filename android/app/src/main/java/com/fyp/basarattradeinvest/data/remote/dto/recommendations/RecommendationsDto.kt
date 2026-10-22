package com.fyp.basarattradeinvest.data.remote.dto.recommendations

import com.google.gson.annotations.SerializedName

data class RecommendationsListResponseDto(
    @SerializedName("count") val count: Int? = null,
    @SerializedName("total_count") val totalCount: Int? = null,
    @SerializedName("generated_at") val generatedAt: String? = null,
    @SerializedName("risk_profile") val riskProfile: String? = "moderate",
    @SerializedName("recommendations") val recommendations: List<RecommendationItemDto> = emptyList()
)

data class RecommendationItemDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("name") val name: String? = null,
    @SerializedName("sector") val sector: String? = null,
    @SerializedName("summary") val summary: String? = null,
    @SerializedName("decision") val decision: RecommendationDecisionNestedDto? = null,
    @SerializedName("market_data") val marketData: TargetStopMarketDataDto? = null,
    @SerializedName("risk") val risk: TargetStopRiskDto? = null,
    @SerializedName("components") val components: Map<String, RecommendationComponentDto>? = null,
    // Flat fields for backward compatibility
    @SerializedName("signal") val signal: String? = null,
    @SerializedName("confidence") val confidence: Double? = null,
    @SerializedName("composite_score") val compositeScore: Double? = null,
    @SerializedName("target_price") val targetPrice: Double? = null,
    @SerializedName("stop_loss") val stopLoss: Double? = null
) {
    fun getResolvedSignal(): String = signal ?: decision?.signal ?: "HOLD"
    fun getResolvedConfidence(): Double = confidence ?: decision?.confidence ?: 0.50
    fun getResolvedCompositeScore(): Double = compositeScore ?: decision?.compositeScore ?: 0.0
    fun getResolvedTargetPrice(): Double? = targetPrice ?: risk?.targetPrice
    fun getResolvedStopLoss(): Double? = stopLoss ?: risk?.stopLoss
    fun getResolvedCurrentPrice(): Double? = marketData?.currentPrice
}

data class RecommendationComponentDto(
    @SerializedName("score") val score: Double? = null,
    @SerializedName("status") val status: String? = null,
    @SerializedName("availability_reason") val availabilityReason: String? = null,
    @SerializedName("configured_weight") val configuredWeight: Double? = null,
    @SerializedName("effective_weight") val effectiveWeight: Double? = null,
    @SerializedName("details") val details: Map<String, Any>? = null
)
