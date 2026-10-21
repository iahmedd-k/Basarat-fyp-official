package com.fyp.basarattradeinvest.feature.auth

sealed interface AuthUiState {
    data object Idle : AuthUiState
    data object Loading : AuthUiState
    data class Success(
        val message: String? = null,
        val userEmail: String? = null,
        // True when the backend already issued tokens for this result. Sign Up uses it to
        // skip email verification, because Google-verified accounts arrive pre-verified.
        val isAuthenticated: Boolean = false
    ) : AuthUiState
    data class Error(val message: String) : AuthUiState
}
