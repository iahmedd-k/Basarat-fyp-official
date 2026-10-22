package com.fyp.basarattradeinvest.feature.community.notifications

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.core.notifications.NotificationBadgeState
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotification
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import com.fyp.basarattradeinvest.domain.usecase.community.GetCommunityNotificationsUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetUnreadCommunityNotificationCountUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.MarkAllCommunityNotificationsReadUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.MarkCommunityNotificationReadUseCase
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CommunityNotificationsViewModel(
    private val getNotificationsUseCase: GetCommunityNotificationsUseCase,
    private val getUnreadCountUseCase: GetUnreadCommunityNotificationCountUseCase,
    private val markReadUseCase: MarkCommunityNotificationReadUseCase,
    private val markAllReadUseCase: MarkAllCommunityNotificationsReadUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow<CommunityNotificationsUiState>(CommunityNotificationsUiState.Loading)
    val uiState: StateFlow<CommunityNotificationsUiState> = _uiState.asStateFlow()

    private var currentUnreadOnly: Boolean = false

    fun loadNotifications(unreadOnly: Boolean = false, isRefresh: Boolean = false) {
        currentUnreadOnly = unreadOnly
        viewModelScope.launch {
            if (!isRefresh && _uiState.value !is CommunityNotificationsUiState.Success) {
                _uiState.value = CommunityNotificationsUiState.Loading
            }

            val notifsDeferred = async { getNotificationsUseCase(page = 1, limit = 50, unreadOnly = unreadOnly) }
            val unreadDeferred = async { getUnreadCountUseCase() }
            val notifsResult = notifsDeferred.await()
            val unreadResult = unreadDeferred.await()

            val unreadCount = unreadResult.getOrNull()?.unreadCount ?: 0

            if (notifsResult.isSuccess) {
                val notifList = notifsResult.getOrNull()!!
                if (notifList.notifications.isEmpty()) {
                    _uiState.value = CommunityNotificationsUiState.Empty
                } else {
                    _uiState.value = CommunityNotificationsUiState.Success(
                        notifications = notifList.notifications,
                        unreadCount = unreadCount,
                        total = notifList.total,
                        isUnreadFilterActive = unreadOnly,
                        isRefreshing = false
                    )
                }
            } else {
                val msg = notifsResult.exceptionOrNull()?.message ?: "Unable to load community notifications"
                _uiState.value = CommunityNotificationsUiState.Error(msg)
            }
        }
    }

    fun markAsRead(notificationId: String) {
        viewModelScope.launch {
            val currentState = _uiState.value
            if (currentState !is CommunityNotificationsUiState.Success ||
                currentState.notifications.none { it.id == notificationId && !it.isRead }
            ) return@launch

            val updatedList = currentState.notifications.map {
                if (it.id == notificationId) it.copy(isRead = true) else it
            }
            val newUnread = maxOf(0, currentState.unreadCount - 1)
            _uiState.value = currentState.copy(
                notifications = updatedList,
                unreadCount = newUnread
            )

            val result = markReadUseCase(notificationId)
            if (result.isSuccess) NotificationBadgeState.markCommunityRead()
            else loadNotifications(unreadOnly = currentUnreadOnly, isRefresh = true)
        }
    }

    fun markAllAsRead() {
        viewModelScope.launch {
            val currentState = _uiState.value
            if (currentState is CommunityNotificationsUiState.Success) {
                val updatedList = currentState.notifications.map { it.copy(isRead = true) }
                _uiState.value = currentState.copy(
                    notifications = updatedList,
                    unreadCount = 0
                )
            }

            // Sync with backend authoritative endpoint
            val result = markAllReadUseCase()
            if (result.isSuccess) {
                NotificationBadgeState.refresh()
                loadNotifications(unreadOnly = currentUnreadOnly, isRefresh = true)
            }
        }
    }

    class Factory(
        private val repository: CommunityRepository = CommunityRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(CommunityNotificationsViewModel::class.java)) {
                return CommunityNotificationsViewModel(
                    getNotificationsUseCase = GetCommunityNotificationsUseCase(repository),
                    getUnreadCountUseCase = GetUnreadCommunityNotificationCountUseCase(repository),
                    markReadUseCase = MarkCommunityNotificationReadUseCase(repository),
                    markAllReadUseCase = MarkAllCommunityNotificationsReadUseCase(repository)
                ) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class")
        }
    }
}
