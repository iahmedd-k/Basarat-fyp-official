package com.fyp.basarattradeinvest.feature.alerts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AlertsRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem
import com.fyp.basarattradeinvest.domain.usecase.alerts.GetAlertsUseCase
import com.fyp.basarattradeinvest.domain.usecase.alerts.MarkAlertReadUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AlertsViewModel(
    private val getAlertsUseCase: GetAlertsUseCase = GetAlertsUseCase(AlertsRepositoryImpl()),
    private val markAlertReadUseCase: MarkAlertReadUseCase = MarkAlertReadUseCase(AlertsRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<AlertsUiState>(AlertsUiState.Loading)
    val uiState: StateFlow<AlertsUiState> = _uiState.asStateFlow()

    private var cachedAlerts: List<AlertItem> = emptyList()
    private var unreadFilter = false

    init {
        loadData()
    }

    fun loadData(isSwipeRefresh: Boolean = false) {
        viewModelScope.launch {
            if (!isSwipeRefresh && cachedAlerts.isEmpty()) {
                _uiState.value = AlertsUiState.Loading
            }

            val result = getAlertsUseCase(page = 1, limit = 50, unreadOnly = null)
            result.fold(
                onSuccess = { alerts ->
                    cachedAlerts = alerts
                    emitContent()
                },
                onFailure = { error ->
                    if (cachedAlerts.isEmpty()) {
                        _uiState.value = AlertsUiState.Error(
                            error.message ?: "Unable to load alert history. Please try again."
                        )
                    } else {
                        emitContent(actionMessage = error.message ?: "Unable to refresh alert history")
                    }
                }
            )
        }
    }

    fun toggleUnreadFilter(unreadOnly: Boolean) {
        unreadFilter = unreadOnly
        emitContent()
    }

    fun markAlertAsRead(alertId: String) {
        val previousAlerts = cachedAlerts
        cachedAlerts = cachedAlerts.map { if (it.id == alertId) it.copy(isRead = true) else it }
        emitContent()

        viewModelScope.launch {
            val result = markAlertReadUseCase(alertId)
            if (result.isFailure) {
                cachedAlerts = previousAlerts
                emitContent(
                    actionMessage = result.exceptionOrNull()?.message
                        ?: "Unable to mark this alert as read"
                )
            }
        }
    }

    fun clearActionMessage() {
        val state = _uiState.value
        if (state is AlertsUiState.Success) {
            _uiState.value = state.copy(actionMessage = null)
        }
    }

    private fun emitContent(actionMessage: String? = null) {
        if (cachedAlerts.isEmpty()) {
            _uiState.value = AlertsUiState.Empty("Price alerts will appear here after the backend triggers them.")
        } else {
            _uiState.value = AlertsUiState.Success(
                alerts = cachedAlerts,
                unreadOnlyFilter = unreadFilter,
                actionMessage = actionMessage
            )
        }
    }
}
