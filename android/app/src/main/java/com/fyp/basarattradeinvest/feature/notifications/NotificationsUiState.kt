package com.fyp.basarattradeinvest.feature.notifications

import com.fyp.basarattradeinvest.domain.model.alerts.InAppNotification

sealed interface NotificationsUiState {
    data object Loading : NotificationsUiState

    data class Success(
        val items: List<InAppNotification>,
        val total: Int,
        val page: Int,
        val hasMore: Boolean,
        val unreadOnlyFilter: Boolean = false,
        val isPaginating: Boolean = false
    ) : NotificationsUiState {
        val unreadCount: Int
            get() = items.count { !it.isRead }
    }

    data class Empty(
        val unreadOnlyFilter: Boolean
    ) : NotificationsUiState

    data class Error(
        val message: String
    ) : NotificationsUiState
}
