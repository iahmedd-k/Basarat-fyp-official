package com.fyp.basarattradeinvest.core.notifications

import kotlinx.coroutines.async
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

object NotificationEvents {
    private val _foregroundNotifications = MutableSharedFlow<NotificationTarget>(
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val foregroundNotifications = _foregroundNotifications.asSharedFlow()

    fun publish(target: NotificationTarget) {
        _foregroundNotifications.tryEmit(target)
    }
}

object NotificationBadgeState {
    private val _unreadCount = MutableStateFlow(0)
    val unreadCount = _unreadCount.asStateFlow()
    private var alertUnreadCount = 0
    private var communityUnreadCount = 0

    // Called from several lifecycle points (activity resume, auth state change, incoming
    // notification), so a cold start used to issue duplicate round trips. Share one pass and
    // loop for requests that arrive while it is running so the final state is still fetched.
    private var isRefreshing = false
    private var rerunRequested = false

    suspend fun refresh() {
        if (isRefreshing) {
            rerunRequested = true
            return
        }
        isRefreshing = true
        try {
            do {
                rerunRequested = false
                coroutineScope {
                    val alerts = async {
                        com.fyp.basarattradeinvest.data.repository.NotificationsRepositoryImpl()
                            .getNotifications(page = 1, limit = 1, unreadOnly = true)
                    }
                    val community = async {
                        com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl()
                            .getUnreadNotificationCount()
                    }
                    alerts.await().getOrNull()?.let { alertUnreadCount = it.total.coerceAtLeast(0) }
                    community.await().getOrNull()?.let { communityUnreadCount = it.unreadCount.coerceAtLeast(0) }
                }
                _unreadCount.value = alertUnreadCount + communityUnreadCount
            } while (rerunRequested)
        } finally {
            isRefreshing = false
        }
    }

    fun markRead() {
        alertUnreadCount = (alertUnreadCount - 1).coerceAtLeast(0)
        _unreadCount.value = alertUnreadCount + communityUnreadCount
    }

    fun markCommunityRead() {
        communityUnreadCount = (communityUnreadCount - 1).coerceAtLeast(0)
        _unreadCount.value = alertUnreadCount + communityUnreadCount
    }

    fun reset() {
        alertUnreadCount = 0
        communityUnreadCount = 0
        _unreadCount.value = 0
    }
}
