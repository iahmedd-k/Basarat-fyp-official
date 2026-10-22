package com.fyp.basarattradeinvest.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.auth.ForgotPasswordUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ForgotPasswordViewModel(
    private val forgotPasswordUseCase: ForgotPasswordUseCase = ForgotPasswordUseCase(AuthRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun requestPasswordReset(email: String) {
        val trimmedEmail = email.trim()
        if (trimmedEmail.isBlank()) {
            _uiState.value = AuthUiState.Error("Please enter your email address")
            return
        }
        if (!android.util.Patterns.EMAIL_ADDRESS.matcher(trimmedEmail).matches()) {
            _uiState.value = AuthUiState.Error("Please enter a valid email address")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = forgotPasswordUseCase(trimmedEmail)
            result.fold(
                onSuccess = {
                    _uiState.value = AuthUiState.Success(
                        message = "If an account exists for $trimmedEmail, a reset token has been dispatched to your email.",
                        userEmail = trimmedEmail
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Failed to request password reset. Please try again."
                    )
                }
            )
        }
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }
}
