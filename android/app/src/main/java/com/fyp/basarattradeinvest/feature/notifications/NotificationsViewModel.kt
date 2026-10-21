package com.fyp.basarattradeinvest.feature.notifications

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.NotificationsRepositoryImpl
import com.fyp.basarattradeinvest.core.notifications.NotificationBadgeState
import com.fyp.basarattradeinvest.domain.model.alerts.InAppNotification
import com.fyp.basarattradeinvest.domain.usecase.notifications.GetNotificationsUseCase
import com.fyp.basarattradeinvest.domain.usecase.notifications.MarkNotificationReadUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class NotificationsViewModel(
    private val getNotificationsUseCase: GetNotificationsUseCase = GetNotificationsUseCase(NotificationsRepositoryImpl()),
    private val markNotificationReadUseCase: MarkNotificationReadUseCase = MarkNotificationReadUseCase(NotificationsRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<NotificationsUiState>(NotificationsUiState.Loading)
    val uiState: StateFlow<NotificationsUiState> = _uiState.asStateFlow()

    private var currentPage = 1
    private val pageSize = 20
    private var hasMorePages = false
    private var isPaginating = false
    private var unreadFilter = false

    private val notificationList = mutableListOf<InAppNotification>()
    private val readRequestsInFlight = mutableSetOf<String>()
    private var totalCount = 0

    init {
        loadInitialNotifications()
    }

    fun loadInitialNotifications(unreadOnly: Boolean = unreadFilter) {
        unreadFilter = unreadOnly
        currentPage = 1
        viewModelScope.launch {
            _uiState.value = NotificationsUiState.Loading

            val result = getNotificationsUseCase(
                page = currentPage,
                limit = pageSize,
                unreadOnly = if (unreadFilter) true else null
            )

            if (result.isSuccess) {
                val feed = result.getOrNull()!!
                notificationList.clear()
                notificationList.addAll(feed.items)
                totalCount = feed.total
                currentPage = feed.page
                hasMorePages = feed.hasMore

                if (notificationList.isEmpty()) {
                    _uiState.value = NotificationsUiState.Empty(unreadOnlyFilter = unreadFilter)
                } else {
                    _uiState.value = NotificationsUiState.Success(
                        items = notificationList.toList(),
                        total = totalCount,
                        page = currentPage,
                        hasMore = hasMorePages,
                        unreadOnlyFilter = unreadFilter,
                        isPaginating = false
                    )
                }
            } else {
                val errorMsg = result.exceptionOrNull()?.message ?: "Unable to load notifications. Please try again."
                _uiState.value = NotificationsUiState.Error(errorMsg)
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            val result = getNotificationsUseCase(
                page = 1,
                limit = pageSize,
                unreadOnly = if (unreadFilter) true else null
            )

            if (result.isSuccess) {
                val feed = result.getOrNull()!!
                notificationList.clear()
                notificationList.addAll(feed.items)
                totalCount = feed.total
                currentPage = feed.page
                hasMorePages = feed.hasMore

                if (notificationList.isEmpty()) {
                    _uiState.value = NotificationsUiState.Empty(unreadOnlyFilter = unreadFilter)
                } else {
                    _uiState.value = NotificationsUiState.Success(
                        items = notificationList.toList(),
                        total = totalCount,
                        page = currentPage,
                        hasMore = hasMorePages,
                        unreadOnlyFilter = unreadFilter,
                        isPaginating = false
                    )
                }
            }
        }
    }

    fun loadNextPage() {
        if (!hasMorePages || isPaginating) return
        isPaginating = true

        val currentSuccess = _uiState.value as? NotificationsUiState.Success
        if (currentSuccess != null) {
            _uiState.value = currentSuccess.copy(isPaginating = true)
        }

        viewModelScope.launch {
            val nextPage = currentPage + 1
            val result = getNotificationsUseCase(
                page = nextPage,
                limit = pageSize,
                unreadOnly = if (unreadFilter) true else null
            )

            isPaginating = false

            if (result.isSuccess) {
                val feed = result.getOrNull()!!
                notificationList.addAll(feed.items)
                totalCount = feed.total
                currentPage = feed.page
                hasMorePages = feed.hasMore

                _uiState.value = NotificationsUiState.Success(
                    items = notificationList.toList(),
                    total = totalCount,
                    page = currentPage,
                    hasMore = hasMorePages,
                    unreadOnlyFilter = unreadFilter,
                    isPaginating = false
                )
            } else {
                // If next page fails, keep existing list and reset isPaginating flag
                if (currentSuccess != null) {
                    _uiState.value = currentSuccess.copy(isPaginating = false)
                }
            }
        }
    }

    fun toggleUnreadFilter(unreadOnly: Boolean) {
        if (unreadFilter == unreadOnly && _uiState.value !is NotificationsUiState.Error) return
        loadInitialNotifications(unreadOnly = unreadOnly)
    }

    fun markAsRead(notificationId: String) {
        val index = notificationList.indexOfFirst { it.id == notificationId }
        if (index == -1 || notificationList[index].isRead || !readRequestsInFlight.add(notificationId)) return

        viewModelScope.launch {
            // Optimistic update in list
            notificationList[index] = notificationList[index].copy(isRead = true)

            // If filter is unreadOnly, remove from displayed list.
            val updatedItems = if (unreadFilter) {
                notificationList.filter { !it.isRead }
            } else {
                notificationList.toList()
            }

            if (updatedItems.isEmpty()) {
                _uiState.value = NotificationsUiState.Empty(unreadOnlyFilter = unreadFilter)
            } else {
                _uiState.value = NotificationsUiState.Success(
                    items = updatedItems,
                    total = totalCount,
                    page = currentPage,
                    hasMore = hasMorePages,
                    unreadOnlyFilter = unreadFilter,
                    isPaginating = false
                )
            }

            val result = markNotificationReadUseCase(notificationId)
            readRequestsInFlight.remove(notificationId)
            if (result.isSuccess) {
                NotificationBadgeState.markRead()
            } else {
                notificationList[index] = notificationList[index].copy(isRead = false)
                _uiState.value = NotificationsUiState.Success(
                    items = if (unreadFilter) notificationList.filter { !it.isRead } else notificationList.toList(),
                    total = totalCount,
                    page = currentPage,
                    hasMore = hasMorePages,
                    unreadOnlyFilter = unreadFilter,
                    isPaginating = false
                )
                NotificationBadgeState.refresh()
            }
        }
    }
}
