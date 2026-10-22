package com.fyp.basarattradeinvest.data.remote.dto.forecast

import com.google.gson.annotations.SerializedName

/**
 * Exact Swagger DTO for GET /api/v1/forecast/{symbol}
 */
data class ForecastResponseDto(
    @SerializedName("symbol")
    val symbol: String? = null,

    @SerializedName("horizon")
    val horizon: String? = null,

    @SerializedName("direction")
    val direction: String? = null,

    @SerializedName("confidence")
    val confidence: Double = 0.0,

    @SerializedName("current_price")
    val currentPrice: Double? = null,

    @SerializedName("target_price")
    val targetPrice: Double? = null,

    @SerializedName("target_date")
    val targetDate: String? = null,

    @SerializedName("as_of_date")
    val asOfDate: String? = null,

    @SerializedName("stop_loss")
    val stopLoss: Double? = null,

    @SerializedName("upside_pct")
    val upsidePct: Double? = null,

    @SerializedName("downside_pct")
    val downsidePct: Double? = null,

    @SerializedName("risk_reward_ratio")
    val riskRewardRatio: Double? = null,

    @SerializedName("signal_rating")
    val signalRating: String? = null,

    @SerializedName("model_version")
    val modelVersion: String? = null,

    @SerializedName("gate_reason")
    val gateReason: String? = null,

    @SerializedName("probabilities")
    val probabilities: ForecastProbabilitiesDto? = null,

    @SerializedName("models")
    val models: Map<String, ForecastModelDetailDto>? = null,

    @SerializedName("market_context")
    val marketContext: ForecastMarketContextDto? = null
)

data class ForecastProbabilitiesDto(
    @SerializedName("bullish")
    val bullish: Double? = null,

    @SerializedName("bearish")
    val bearish: Double? = null,

    @SerializedName("sideways")
    val sideways: Double? = null
)

data class ForecastModelDetailDto(
    @SerializedName("direction")
    val direction: String? = null,

    @SerializedName("bullish_pct")
    val bullishPct: Double? = null,

    @SerializedName("bearish_pct")
    val bearishPct: Double? = null,

    @SerializedName("sideways_pct")
    val sidewaysPct: Double? = null,

    @SerializedName("gap_pp")
    val gapPp: Double? = null
)

data class ForecastMarketContextDto(
    @SerializedName("market_return_5d")
    val marketReturn5d: Double? = null,

    @SerializedName("market_return_20d")
    val marketReturn20d: Double? = null,

    @SerializedName("stock_return_20d")
    val stockReturn20d: Double? = null,

    @SerializedName("stock_relative_return_20d")
    val stockRelativeReturn20d: Double? = null
)
