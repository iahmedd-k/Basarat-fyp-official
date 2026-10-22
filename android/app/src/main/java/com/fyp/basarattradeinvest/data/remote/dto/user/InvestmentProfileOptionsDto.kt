package com.fyp.basarattradeinvest.data.remote.dto.user

import com.google.gson.annotations.SerializedName

/**
 * Exact response schema from GET /api/v1/users/investment-profile/options
 */
data class InvestmentProfileOptionsDto(
    @SerializedName("risk_tolerances")
    val riskTolerances: List<String> = emptyList(),

    @SerializedName("investment_horizons")
    val investmentHorizons: List<String> = emptyList(),

    @SerializedName("sectors")
    val sectors: List<String> = emptyList(),

    @SerializedName("no_preference")
    val noPreference: String? = "All Sectors",

    @SerializedName("description")
    val description: String? = null
)
