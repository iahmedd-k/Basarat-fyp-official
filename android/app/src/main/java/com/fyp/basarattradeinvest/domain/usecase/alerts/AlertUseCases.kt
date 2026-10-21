package com.fyp.basarattradeinvest.domain.usecase.alerts

import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem
import com.fyp.basarattradeinvest.domain.repository.AlertsRepository

class GetAlertsUseCase(private val repository: AlertsRepository) {
    suspend operator fun invoke(
        page: Int? = 1,
        limit: Int? = 50,
        unreadOnly: Boolean? = null
    ): Result<List<AlertItem>> {
        return repository.getAlerts(page, limit, unreadOnly)
    }
}

class MarkAlertReadUseCase(private val repository: AlertsRepository) {
    suspend operator fun invoke(alertId: String): Result<Unit> {
        return repository.markAlertAsRead(alertId)
    }
}
