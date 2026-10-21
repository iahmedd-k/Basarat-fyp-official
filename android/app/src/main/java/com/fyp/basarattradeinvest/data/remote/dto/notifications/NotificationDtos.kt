package com.fyp.basarattradeinvest.data.remote.dto.notifications

import com.google.gson.annotations.SerializedName

/**
 * Exact OpenAPI schema for single notification item in NotificationsListResponse
 * Matches #/components/schemas/AlertResponse
 */
data class NotificationItemDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("user_id")
    val userId: String,

    @SerializedName("rule_id")
    val ruleId: String? = null,

    @SerializedName("title")
    val title: String,

    @SerializedName("message")
    val message: String? = null,

    @SerializedName("is_read")
    val isRead: Boolean,

    @SerializedName("created_at")
    val createdAt: String
)

/**
 * Exact OpenAPI schema for NotificationsListResponse
 * Returned by GET /api/v1/notifications
 */
data class NotificationsListResponseDto(
    @SerializedName("notifications")
    val notifications: List<NotificationItemDto>,

    @SerializedName("total")
    val total: Int,

    @SerializedName("page")
    val page: Int,

    @SerializedName("limit")
    val limit: Int,

    @SerializedName("has_more")
    val hasMore: Boolean
)
