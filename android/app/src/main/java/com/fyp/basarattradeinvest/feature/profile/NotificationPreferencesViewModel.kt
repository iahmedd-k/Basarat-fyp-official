package com.fyp.basarattradeinvest.feature.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateNotificationPrefsRequestDto
import com.fyp.basarattradeinvest.data.repository.UsersRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.user.UpdateNotificationPreferencesUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class NotificationPreferencesViewModel(
    private val updateNotificationPreferencesUseCase: UpdateNotificationPreferencesUseCase = UpdateNotificationPreferencesUseCase(UsersRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<NotificationPrefsUiState>(NotificationPrefsUiState.Idle)
    val uiState: StateFlow<NotificationPrefsUiState> = _uiState.asStateFlow()

    fun savePreferences(
        channels: List<String>,
        categories: List<String>
    ) {
        viewModelScope.launch {
            _uiState.value = NotificationPrefsUiState.Loading

            val request = UpdateNotificationPrefsRequestDto(
                channels = channels,
                categories = categories
            )

            val result = updateNotificationPreferencesUseCase(request)
            result.fold(
                onSuccess = {
                    _uiState.value = NotificationPrefsUiState.Success(
                        message = "Notification preferences updated successfully!"
                    )
                },
                onFailure = { error ->
                    _uiState.value = NotificationPrefsUiState.Error(
                        error.message ?: "Failed to update notification preferences. Please try again."
                    )
                }
            )
        }
    }

    fun resetState() {
        _uiState.value = NotificationPrefsUiState.Idle
    }
}
