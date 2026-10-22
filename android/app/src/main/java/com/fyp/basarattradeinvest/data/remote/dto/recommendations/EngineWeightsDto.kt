package com.fyp.basarattradeinvest.data.remote.dto.recommendations

import com.google.gson.annotations.SerializedName

data class EngineWeightsResponseDto(
    @SerializedName("weights") val weights: Map<String, Double>? = null,
    // Retain the previous response fields while older backend instances roll forward.
    @SerializedName("gru_weight") val gruWeight: Double = 0.0,
    @SerializedName("technical_weight") val technicalWeight: Double = 0.0,
    @SerializedName("fundamental_weight") val fundamentalWeight: Double = 0.0
)

data class EngineWeightsRequestDto(
    @SerializedName("gru_weight") val gruWeight: Double,
    @SerializedName("ml_weight") val mlWeight: Double? = null,
    @SerializedName("technical_weight") val technicalWeight: Double,
    @SerializedName("fundamental_weight") val fundamentalWeight: Double,
    @SerializedName("sentiment_weight") val sentimentWeight: Double = 0.0
)
