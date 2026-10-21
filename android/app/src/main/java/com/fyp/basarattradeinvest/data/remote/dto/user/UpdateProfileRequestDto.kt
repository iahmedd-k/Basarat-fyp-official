package com.fyp.basarattradeinvest.data.remote.dto.user

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for UpdateProfileRequest
 * Used by POST /api/v1/users/me and PATCH /api/v1/users/me
 */
data class UpdateProfileRequestDto(
    @SerializedName("full_name")
    val fullName: String? = null,

    @SerializedName("avatar_url")
    val avatarUrl: String? = null,

    @SerializedName("risk_tolerance")
    val riskTolerance: String? = null,

    @SerializedName("sector_preferences")
    val sectorPreferences: List<String>? = null,

    @SerializedName("investment_horizon")
    val investmentHorizon: String? = null
)
