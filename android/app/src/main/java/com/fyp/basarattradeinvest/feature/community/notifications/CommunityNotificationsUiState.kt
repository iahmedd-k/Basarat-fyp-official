package com.fyp.basarattradeinvest.feature.community.notifications

import com.fyp.basarattradeinvest.domain.model.community.CommunityNotification

sealed interface CommunityNotificationsUiState {
    data object Loading : CommunityNotificationsUiState

    data class Success(
        val notifications: List<CommunityNotification>,
        val unreadCount: Int,
        val total: Int,
        val isUnreadFilterActive: Boolean,
        val isRefreshing: Boolean = false
    ) : CommunityNotificationsUiState

    data object Empty : CommunityNotificationsUiState

    data class Error(
        val message: String
    ) : CommunityNotificationsUiState
}
