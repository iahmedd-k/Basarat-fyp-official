package com.fyp.basarattradeinvest.domain.usecase.notifications

import com.fyp.basarattradeinvest.domain.model.alerts.NotificationFeed
import com.fyp.basarattradeinvest.domain.repository.NotificationsRepository

class GetNotificationsUseCase(private val repository: NotificationsRepository) {
    suspend operator fun invoke(
        page: Int? = 1,
        limit: Int? = 20,
        unreadOnly: Boolean? = null
    ): Result<NotificationFeed> {
        return repository.getNotifications(page, limit, unreadOnly)
    }
}

class MarkNotificationReadUseCase(private val repository: NotificationsRepository) {
    suspend operator fun invoke(notificationId: String): Result<Unit> {
        return repository.markNotificationAsRead(notificationId)
    }
}
