package com.fyp.basarattradeinvest.feature.profile

sealed interface NotificationPrefsUiState {
    data object Idle : NotificationPrefsUiState
    data object Loading : NotificationPrefsUiState
    data class Success(val message: String) : NotificationPrefsUiState
    data class Error(val message: String) : NotificationPrefsUiState
}
