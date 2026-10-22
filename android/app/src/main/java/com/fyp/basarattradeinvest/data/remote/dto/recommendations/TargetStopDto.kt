package com.fyp.basarattradeinvest.data.remote.dto.recommendations

import com.google.gson.annotations.SerializedName

data class TargetStopResponseDto(
    @SerializedName("symbol") val symbol: String,
    @SerializedName("current_price") val currentPrice: Double? = null,
    @SerializedName("target_price") val targetPrice: Double? = null,
    @SerializedName("stop_loss") val stopLoss: Double? = null,
    @SerializedName("expected_range") val expectedRange: Map<String, Any>? = null,
    @SerializedName("method") val method: String? = null,
    @SerializedName("atr_14") val atr14: Double? = null,
    @SerializedName("risk_tolerance") val riskTolerance: String? = null,
    @SerializedName("risk_profile") val riskProfile: String? = null,
    @SerializedName("upside_pct") val upsidePct: Double? = null,
    @SerializedName("downside_pct") val downsidePct: Double? = null,
    @SerializedName("risk") val risk: TargetStopRiskDto? = null,
    @SerializedName("market_data") val marketData: TargetStopMarketDataDto? = null,
    @SerializedName("decision") val decision: Map<String, Any>? = null
) {
    fun getResolvedCurrentPrice(): Double? = currentPrice ?: marketData?.currentPrice
    fun getResolvedTargetPrice(): Double? = targetPrice ?: risk?.targetPrice
    fun getResolvedStopLoss(): Double? = stopLoss ?: risk?.stopLoss
    fun getResolvedExpectedRange(): Map<String, Any>? = expectedRange ?: risk?.expectedRange
    fun getResolvedMethod(): String? = method ?: risk?.method ?: "atr_band"
    fun getResolvedAtr14(): Double? = atr14 ?: risk?.atr14
    fun getResolvedRiskTolerance(): String? = riskTolerance ?: riskProfile ?: "moderate"
    fun getResolvedUpsidePct(): Double? = upsidePct ?: risk?.upsidePct
    fun getResolvedDownsidePct(): Double? = downsidePct ?: risk?.downsidePct
}

data class TargetStopRiskDto(
    @SerializedName("target_price") val targetPrice: Double? = null,
    @SerializedName("stop_loss") val stopLoss: Double? = null,
    @SerializedName("expected_range") val expectedRange: Map<String, Any>? = null,
    @SerializedName("method") val method: String? = null,
    @SerializedName("atr_14") val atr14: Double? = null,
    @SerializedName("upside_pct") val upsidePct: Double? = null,
    @SerializedName("downside_pct") val downsidePct: Double? = null,
    @SerializedName("risk_reward_ratio") val riskRewardRatio: Double? = null,
    @SerializedName("explanation") val explanation: String? = null
)

data class TargetStopMarketDataDto(
    @SerializedName("current_price") val currentPrice: Double? = null
)
