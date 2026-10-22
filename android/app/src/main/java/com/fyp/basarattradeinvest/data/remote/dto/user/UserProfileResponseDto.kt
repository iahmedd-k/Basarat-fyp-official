package com.fyp.basarattradeinvest.data.remote.dto.user

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for UserProfileResponse
 * Returned by GET /api/v1/users/me, POST /api/v1/users/me, PATCH /api/v1/users/me
 */
data class UserProfileResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("email")
    val email: String,

    @SerializedName("username")
    val username: String,

    @SerializedName("full_name")
    val fullName: String? = null,

    @SerializedName("avatar_url")
    val avatarUrl: String? = null,

    @SerializedName("is_active")
    val isActive: Boolean,

    @SerializedName("is_verified")
    val isVerified: Boolean,

    @SerializedName("risk_tolerance")
    val riskTolerance: String? = null,

    @SerializedName("sector_preferences")
    val sectorPreferences: List<String>? = null,

    @SerializedName("investment_horizon")
    val investmentHorizon: String? = null,

    @SerializedName("created_at")
    val createdAt: String
)
