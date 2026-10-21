package com.fyp.basarattradeinvest.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.AuthRepository
import com.fyp.basarattradeinvest.domain.usecase.auth.GoogleSignInUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.SignUpUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SignUpViewModel(
    private val authRepository: AuthRepository = AuthRepositoryImpl(),
    private val signUpUseCase: SignUpUseCase = SignUpUseCase(authRepository),
    private val googleSignInUseCase: GoogleSignInUseCase = GoogleSignInUseCase(authRepository)
) : ViewModel() {

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun signUp(name: String, email: String, password: String, confirmPassword: String? = null) {
        val trimmedName = name.trim()
        val trimmedEmail = email.trim()

        if (trimmedName.isBlank()) {
            _uiState.value = AuthUiState.Error("Please enter your name")
            return
        }
        if (trimmedEmail.isBlank()) {
            _uiState.value = AuthUiState.Error("Please enter your email")
            return
        }
        if (!android.util.Patterns.EMAIL_ADDRESS.matcher(trimmedEmail).matches()) {
            _uiState.value = AuthUiState.Error("Please enter a valid email address")
            return
        }
        if (password.length < 8) {
            _uiState.value = AuthUiState.Error("Password must be at least 8 characters")
            return
        }
        if (confirmPassword != null && confirmPassword.isBlank()) {
            _uiState.value = AuthUiState.Error("Please confirm your password")
            return
        }
        if (confirmPassword != null && password != confirmPassword) {
            _uiState.value = AuthUiState.Error("Passwords do not match")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val result = signUpUseCase(
                email = trimmedEmail,
                password = password,
                fullName = trimmedName
            )
            result.fold(
                onSuccess = { message ->
                    _uiState.value = AuthUiState.Success(
                        message = message,
                        userEmail = trimmedEmail
                    )
                },
                onFailure = { throwable ->
                    _uiState.value = AuthUiState.Error(
                        throwable.message ?: "Sign up failed. Please try again."
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
                        message = "Signed in with Google",
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
