package com.fyp.basarattradeinvest.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.auth.ResetPasswordUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ResetPasswordViewModel(
    private val resetPasswordUseCase: ResetPasswordUseCase = ResetPasswordUseCase(AuthRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun resetPassword(resetToken: String, newPassword: String, confirmPassword: String) {
        val trimmedToken = resetToken.trim()
        if (trimmedToken.isBlank()) {
            _uiState.value = AuthUiState.Error("Reset token grant is missing. Please restart the reset process.")
            return
        }
        if (newPassword.length < 8) {
            _uiState.value = AuthUiState.Error("New password must be at least 8 characters")
            return
        }
        if (newPassword != confirmPassword) {
            _uiState.value = AuthUiState.Error("Passwords do not match")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = resetPasswordUseCase(trimmedToken, newPassword, confirmPassword)
            result.fold(
                onSuccess = { message ->
                    _uiState.value = AuthUiState.Success(
                        message = message.ifBlank { "Password successfully reset! Please sign in with your new password." }
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Failed to reset password. The grant may have expired."
                    )
                }
            )
        }
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }
}
