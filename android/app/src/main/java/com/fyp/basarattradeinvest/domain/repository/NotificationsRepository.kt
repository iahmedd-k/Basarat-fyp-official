package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.alerts.NotificationFeed

interface NotificationsRepository {

    /**
     * Get user notifications with optional pagination and unread filter.
     */
    suspend fun getNotifications(
        page: Int? = 1,
        limit: Int? = 20,
        unreadOnly: Boolean? = null
    ): Result<NotificationFeed>

    /**
     * Mark a notification as read.
     */
    suspend fun markNotificationAsRead(notificationId: String): Result<Unit>
}
