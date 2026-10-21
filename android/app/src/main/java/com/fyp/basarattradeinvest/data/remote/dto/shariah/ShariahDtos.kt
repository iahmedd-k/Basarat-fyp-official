package com.fyp.basarattradeinvest.data.remote.dto.shariah

import com.google.gson.annotations.SerializedName

/**
 * Data Transfer Objects for Shariah Module.
 * Field names match the live schema at /api/v1/openapi.json
 * (components.schemas.ShariahKMI30Response / ShariahScreeningResponse /
 * ShariahCriteriaResponse / ShariahPurificationResponse).
 */

data class ShariahKmi30ResponseDto(
    @SerializedName("index")
    val index: String? = null,

    @SerializedName("total_constituents")
    val totalConstituents: Int? = null,

    @SerializedName("as_of")
    val asOf: String? = null,

    @SerializedName("is_stale")
    val isStale: Boolean = false,

    @SerializedName("effective_from")
    val effectiveFrom: String? = null,

    @SerializedName("source_url")
    val sourceUrl: String? = null,

    @SerializedName("constituents")
    val constituents: List<Kmi30ConstituentDto> = emptyList()
)

/**
 * The KMI-30 Shariah list carries screening ratios only — it has no price, change,
 * weight or sector fields. Quotes come from the live market layer.
 */
data class Kmi30ConstituentDto(
    @SerializedName("symbol")
    val symbol: String,

    @SerializedName("name")
    val name: String? = null,

    @SerializedName("is_shariah_compliant")
    val isShariahCompliant: Boolean? = null,

    @SerializedName("debt_ratio")
    val debtRatio: Double? = null,

    @SerializedName("interest_income_ratio")
    val interestIncomeRatio: Double? = null,

    @SerializedName("data_as_of")
    val dataAsOf: String? = null,

    @SerializedName("purification_rate_provisional")
    val purificationRateProvisional: Boolean = false
)

data class ShariahScreeningResponseDto(
    @SerializedName("symbol")
    val symbol: String,

    @SerializedName("screening_available")
    val screeningAvailable: Boolean = true,

    @SerializedName("is_shariah_compliant")
    val isShariahCompliant: Boolean = true,

    @SerializedName("overall_score")
    val overallScore: Double? = null,

    @SerializedName("screening_method")
    val screeningMethod: String? = null,

    @SerializedName("screened_at")
    val screenedAt: String? = null,

    @SerializedName("data_as_of")
    val dataAsOf: String? = null,

    @SerializedName("data_is_stale")
    val dataIsStale: Boolean = false,

    @SerializedName("effective_from")
    val effectiveFrom: String? = null,

    @SerializedName("source_url")
    val sourceUrl: String? = null,

    @SerializedName("purification_rate_provisional")
    val purificationRateProvisional: Boolean = false,

    @SerializedName("sector")
    val sector: String? = null,

    @SerializedName("purification_rate")
    val purificationRate: Double? = null,

    @SerializedName("compliance_summary")
    val complianceSummary: String? = null
)

data class ShariahCriteriaResponseDto(
    @SerializedName("symbol")
    val symbol: String,

    @SerializedName("screening_available")
    val screeningAvailable: Boolean = true,

    @SerializedName("is_shariah_compliant")
    val isShariahCompliant: Boolean = true,

    @SerializedName("criteria")
    val criteria: List<ShariahCriterionDto> = emptyList(),

    @SerializedName("data_as_of")
    val dataAsOf: String? = null,

    @SerializedName("data_is_stale")
    val dataIsStale: Boolean = false,

    @SerializedName("source_url")
    val sourceUrl: String? = null
)

data class ShariahCriterionDto(
    @SerializedName("name")
    val name: String,

    @SerializedName("threshold")
    val threshold: Double? = null,

    @SerializedName("value")
    val value: Double? = null,

    @SerializedName("passed")
    val passed: Boolean? = null,

    @SerializedName("description")
    val description: String? = null,

    @SerializedName("exception")
    val exception: String? = null
)

data class ShariahPurificationResponseDto(
    @SerializedName("symbol")
    val symbol: String,

    @SerializedName("dividend_income")
    val dividendIncome: Double,

    @SerializedName("purification_amount")
    val purificationAmount: Double,

    @SerializedName("purification_rate")
    val purificationRate: Double,

    @SerializedName("notes")
    val notes: String? = null,

    @SerializedName("data_as_of")
    val dataAsOf: String? = null,

    @SerializedName("data_is_stale")
    val dataIsStale: Boolean = false,

    @SerializedName("rate_is_provisional")
    val rateIsProvisional: Boolean = false
)
