package com.fyp.basarattradeinvest.data.remote.dto.user

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for UpdateNotificationPrefsRequest
 * Used by PATCH /api/v1/users/me/notification-preferences
 */
data class UpdateNotificationPrefsRequestDto(
    @SerializedName("channels")
    val channels: List<String>? = null,

    @SerializedName("categories")
    val categories: List<String>? = null
)
