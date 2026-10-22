package com.fyp.basarattradeinvest.core.session

sealed interface AuthState {
    data object Unknown : AuthState
    data class Authenticated(val userEmail: String, val userName: String? = null) : AuthState
    data object Unauthenticated : AuthState
    data object SessionExpired : AuthState
}

sealed interface SessionEvent {
    data object RefreshTemporarilyUnavailable : SessionEvent
}
