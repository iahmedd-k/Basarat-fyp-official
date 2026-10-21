package com.fyp.basarattradeinvest.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.auth.ForgotPasswordUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.VerifyResetCodeUseCase
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface VerifyResetCodeUiState {
    data object Idle : VerifyResetCodeUiState
    data object Loading : VerifyResetCodeUiState
    data class Success(val resetToken: String, val message: String?) : VerifyResetCodeUiState
    data class Error(val message: String) : VerifyResetCodeUiState
}

class VerifyResetCodeViewModel(
    private val verifyResetCodeUseCase: VerifyResetCodeUseCase = VerifyResetCodeUseCase(AuthRepositoryImpl()),
    private val forgotPasswordUseCase: ForgotPasswordUseCase = ForgotPasswordUseCase(AuthRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<VerifyResetCodeUiState>(VerifyResetCodeUiState.Idle)
    val uiState: StateFlow<VerifyResetCodeUiState> = _uiState.asStateFlow()

    private val _resendFeedback = MutableStateFlow<String?>(null)
    val resendFeedback: StateFlow<String?> = _resendFeedback.asStateFlow()

    private val _cooldownSeconds = MutableStateFlow(60)
    val cooldownSeconds: StateFlow<Int> = _cooldownSeconds.asStateFlow()

    private var timerJob: Job? = null

    init {
        startCooldownTimer(60)
    }

    fun startCooldownTimer(seconds: Int = 60) {
        timerJob?.cancel()
        timerJob = viewModelScope.launch {
            _cooldownSeconds.value = seconds
            while (_cooldownSeconds.value > 0) {
                delay(1000)
                _cooldownSeconds.value -= 1
            }
        }
    }

    fun verifyCode(email: String, code: String) {
        val trimmedEmail = email.trim()
        val trimmedCode = code.trim()

        if (trimmedEmail.isBlank()) {
            _uiState.value = VerifyResetCodeUiState.Error("Email address is missing")
            return
        }
        if (trimmedCode.length != 6) {
            _uiState.value = VerifyResetCodeUiState.Error("Please enter all 6 digits of the reset code")
            return
        }

        viewModelScope.launch {
            _uiState.value = VerifyResetCodeUiState.Loading
            val result = verifyResetCodeUseCase(trimmedEmail, trimmedCode)
            result.fold(
                onSuccess = { res ->
                    _uiState.value = VerifyResetCodeUiState.Success(
                        resetToken = res.resetToken,
                        message = res.message ?: "Code verified successfully"
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = VerifyResetCodeUiState.Error(
                        throwable.message ?: "Code verification failed. Please try again."
                    )
                }
            )
        }
    }

    fun resendCode(email: String) {
        if (_cooldownSeconds.value > 0) return
        val trimmedEmail = email.trim()
        if (trimmedEmail.isBlank()) {
            _uiState.value = VerifyResetCodeUiState.Error("Email address is missing")
            return
        }

        viewModelScope.launch {
            _resendFeedback.value = null
            val result = forgotPasswordUseCase(trimmedEmail)
            result.fold(
                onSuccess = { message ->
                    _resendFeedback.value = message
                    startCooldownTimer(60)
                },
                onFailure = { throwable ->
                    _uiState.value = VerifyResetCodeUiState.Error(
                        throwable.message ?: "Failed to resend reset code. Please try again."
                    )
                }
            )
        }
    }

    fun clearResendFeedback() {
        _resendFeedback.value = null
    }

    fun resetState() {
        _uiState.value = VerifyResetCodeUiState.Idle
    }

    override fun onCleared() {
        super.onCleared()
        timerJob?.cancel()
    }
}
