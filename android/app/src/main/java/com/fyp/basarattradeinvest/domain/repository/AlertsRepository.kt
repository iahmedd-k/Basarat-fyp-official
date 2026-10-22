package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem
import com.fyp.basarattradeinvest.domain.model.alerts.QuickAlertResult

interface AlertsRepository {

    /** Create a backend-managed quick price alert using the stock ticker. */
    suspend fun createQuickAlertRule(symbol: String): Result<QuickAlertResult>

    /**
     * Get user's triggered alerts / notification history.
     */
    suspend fun getAlerts(
        page: Int? = 1,
        limit: Int? = 50,
        unreadOnly: Boolean? = null
    ): Result<List<AlertItem>>

    /**
     * Mark an alert as read.
     */
    suspend fun markAlertAsRead(alertId: String): Result<Unit>
}
