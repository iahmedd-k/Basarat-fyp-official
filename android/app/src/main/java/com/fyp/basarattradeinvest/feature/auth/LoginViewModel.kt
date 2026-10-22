package com.fyp.basarattradeinvest.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.AuthRepository
import com.fyp.basarattradeinvest.domain.usecase.auth.GoogleSignInUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.LoginUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class LoginViewModel(
    private val authRepository: AuthRepository = AuthRepositoryImpl(),
    private val loginUseCase: LoginUseCase = LoginUseCase(authRepository),
    private val googleSignInUseCase: GoogleSignInUseCase = GoogleSignInUseCase(authRepository)
) : ViewModel() {

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun signIn(email: String, password: String) {
        val trimmedEmail = email.trim()
        if (trimmedEmail.isBlank()) {
            _uiState.value = AuthUiState.Error("Please enter your email")
            return
        }
        if (!android.util.Patterns.EMAIL_ADDRESS.matcher(trimmedEmail).matches()) {
            _uiState.value = AuthUiState.Error("Please enter a valid email address")
            return
        }
        if (password.isBlank()) {
            _uiState.value = AuthUiState.Error("Please enter your password")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = loginUseCase(trimmedEmail, password)
            result.fold(
                onSuccess = { session ->
                    _uiState.value = AuthUiState.Success(
                        message = "Welcome back!",
                        userEmail = session.user?.email ?: trimmedEmail
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Authentication failed. Please check your credentials."
                    )
                }
            )
        }
    }

    fun signInWithGoogle(idToken: String) {
        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            googleSignInUseCase(idToken).fold(
                onSuccess = { session ->
                    _uiState.value = AuthUiState.Success(
                        message = "Welcome back!",
                        userEmail = session.user?.email,
                        isAuthenticated = true
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Google sign-in failed. Please try again."
                    )
                }
            )
        }
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }
}
