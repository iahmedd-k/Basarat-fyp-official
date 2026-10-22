package com.fyp.basarattradeinvest.data.remote.dto.risk

import com.google.gson.annotations.SerializedName

data class MonteCarloRequestDto(
    @SerializedName("num_simulations")
    val numSimulations: Int = 1000,

    @SerializedName("horizon_days")
    val horizonDays: Int = 30
)

data class MonteCarloResponseDto(
    @SerializedName("job_id")
    val jobId: String,

    @SerializedName("status")
    val status: String? = "pending",

    @SerializedName("num_simulations")
    val numSimulations: Int? = null,

    @SerializedName("horizon_days")
    val horizonDays: Int? = null,

    @SerializedName("message")
    val message: String? = null
)

data class MonteCarloResultResponseDto(
    @SerializedName("job_id")
    val jobId: String,

    @SerializedName("status")
    val status: String,

    @SerializedName("num_simulations")
    val numSimulations: Int? = null,

    @SerializedName("horizon_days")
    val horizonDays: Int? = null,

    @SerializedName("params")
    val params: Map<String, Any>? = null,

    @SerializedName("percentiles")
    val percentiles: Map<String, Double>? = null,

    @SerializedName("stats")
    val stats: Map<String, Any>? = null,

    @SerializedName("paths_sample")
    val pathsSample: List<List<Double>>? = null,

    @SerializedName("error")
    val error: String? = null,

    @SerializedName("completed_at")
    val completedAt: String? = null
)
