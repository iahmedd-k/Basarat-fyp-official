package com.fyp.basarattradeinvest.data.remote.dto.risk

import com.google.gson.annotations.SerializedName

data class RiskVaRResponseDto(
    @SerializedName("confidence")
    val confidence: Int? = null,

    @SerializedName("horizon")
    val horizon: String? = null,

    @SerializedName("var_value")
    val varValue: Double? = null,

    @SerializedName("cvar_value")
    val cvarValue: Double? = null,

    @SerializedName("method")
    val method: String? = null,

    @SerializedName("num_observations")
    val numObservations: Int? = null,

    @SerializedName("annualized_volatility")
    val annualizedVolatility: Double? = null
)
