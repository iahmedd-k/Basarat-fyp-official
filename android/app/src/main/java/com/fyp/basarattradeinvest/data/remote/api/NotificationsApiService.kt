package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.notifications.NotificationsListResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit service for in-app Notifications endpoints.
 * Source of truth: OpenAPI /api/v1/openapi.json
 */
interface NotificationsApiService {

    /**
     * Get user notifications inbox with pagination and unread filter.
     */
    @GET("api/v1/notifications")
    suspend fun getNotifications(
        @Query("page") page: Int? = null,
        @Query("limit") limit: Int? = null,
        @Query("unread_only") unreadOnly: Boolean? = null
    ): Response<NotificationsListResponseDto>

    /**
     * Mark a notification as read.
     */
    @PATCH("api/v1/notifications/{notification_id}/read")
    suspend fun markNotificationAsRead(
        @Path("notification_id") notificationId: String
    ): Response<Unit>
}
