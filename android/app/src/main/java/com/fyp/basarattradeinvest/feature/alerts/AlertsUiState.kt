package com.fyp.basarattradeinvest.feature.alerts

import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem

sealed interface AlertsUiState {
    data object Loading : AlertsUiState

    data class Success(
        val alerts: List<AlertItem>,
        val unreadOnlyFilter: Boolean = false,
        val actionMessage: String? = null
    ) : AlertsUiState {
        val filteredAlerts: List<AlertItem>
            get() = if (unreadOnlyFilter) alerts.filterNot { it.isRead } else alerts

        val unreadCount: Int
            get() = alerts.count { !it.isRead }
    }

    data class Empty(val message: String) : AlertsUiState
    data class Error(val message: String) : AlertsUiState
}
