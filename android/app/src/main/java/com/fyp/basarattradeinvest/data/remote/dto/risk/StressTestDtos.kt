package com.fyp.basarattradeinvest.data.remote.dto.risk

import com.google.gson.annotations.SerializedName

data class StressTestResponseDto(
    @SerializedName("scenario")
    val scenario: String,

    @SerializedName("name")
    val name: String,

    @SerializedName("description")
    val description: String,

    @SerializedName("portfolio_impact")
    val portfolioImpact: Double,

    @SerializedName("portfolio_impact_value")
    val portfolioImpactValue: Double,

    @SerializedName("worst_case_loss")
    val worstCaseLoss: Double,

    @SerializedName("volatility_multiplier")
    val volatilityMultiplier: Double,

    @SerializedName("recovery_days")
    val recoveryDays: Int,

    @SerializedName("current_value")
    val currentValue: Double,

    @SerializedName("stressed_value")
    val stressedValue: Double,

    @SerializedName("holding_impacts")
    val holdingImpacts: List<Map<String, Any>>? = null
)

data class HoldingImpactDto(
    val symbol: String,
    val name: String? = null,
    val impactPct: Double? = null,
    val impactValue: Double? = null,
    val currentValue: Double? = null,
    val stressedValue: Double? = null
)
