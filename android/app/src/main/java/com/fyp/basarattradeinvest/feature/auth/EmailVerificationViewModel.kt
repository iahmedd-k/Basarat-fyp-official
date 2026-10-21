package com.fyp.basarattradeinvest.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.auth.ResendVerificationUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.VerifyEmailUseCase
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class EmailVerificationViewModel(
    private val verifyEmailUseCase: VerifyEmailUseCase = VerifyEmailUseCase(AuthRepositoryImpl()),
    private val resendVerificationUseCase: ResendVerificationUseCase = ResendVerificationUseCase(AuthRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

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

    fun verifyEmail(email: String, code: String) {
        val trimmedEmail = email.trim()
        val trimmedCode = code.trim()

        if (trimmedEmail.isBlank()) {
            _uiState.value = AuthUiState.Error("Email address is missing")
            return
        }
        if (trimmedCode.length != 6) {
            _uiState.value = AuthUiState.Error("Please enter all 6 digits of the verification code")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = verifyEmailUseCase(trimmedEmail, trimmedCode)
            result.fold(
                onSuccess = { session ->
                    _uiState.value = AuthUiState.Success(
                        message = "Email verified! Welcome to BASARAT.",
                        userEmail = session.user?.email ?: trimmedEmail
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Verification failed. Please check the code."
                    )
                }
            )
        }
    }

    fun resendVerification(email: String) {
        if (_cooldownSeconds.value > 0) return
        val trimmedEmail = email.trim()
        if (trimmedEmail.isBlank()) {
            _uiState.value = AuthUiState.Error("Email address is missing")
            return
        }

        viewModelScope.launch {
            _resendFeedback.value = null
            val result = resendVerificationUseCase(trimmedEmail)
            result.fold(
                onSuccess = { message ->
                    _resendFeedback.value = message
                    startCooldownTimer(60)
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Failed to resend verification code. Please try again."
                    )
                }
            )
        }
    }

    fun clearResendFeedback() {
        _resendFeedback.value = null
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }

    override fun onCleared() {
        super.onCleared()
        timerJob?.cancel()
    }
}
