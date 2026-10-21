package com.fyp.basarattradeinvest.feature.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.auth.ChangePasswordUseCase
import com.fyp.basarattradeinvest.feature.auth.AuthUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ChangePasswordViewModel(
    private val changePasswordUseCase: ChangePasswordUseCase = ChangePasswordUseCase(AuthRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun changePassword(currentPassword: String, newPassword: String, confirmPassword: String) {
        if (currentPassword.isBlank()) {
            _uiState.value = AuthUiState.Error("Please enter your current password")
            return
        }
        if (newPassword.length < 8) {
            _uiState.value = AuthUiState.Error("New password must be at least 8 characters")
            return
        }
        if (newPassword != confirmPassword) {
            _uiState.value = AuthUiState.Error("New passwords do not match")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = changePasswordUseCase(currentPassword, newPassword, confirmPassword)
            result.fold(
                onSuccess = { message ->
                    _uiState.value = AuthUiState.Success(
                        message = message.ifBlank { "Password updated successfully!" }
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Failed to update password. Please verify your current password."
                    )
                }
            )
        }
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }
}
