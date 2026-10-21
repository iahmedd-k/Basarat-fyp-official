package com.fyp.basarattradeinvest.core.session

import android.content.Context
import android.util.Base64
import org.json.JSONObject
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.asSharedFlow

object SessionManager {

    private var tokenStorage: SecureTokenStorage? = null
    private var appContext: Context? = null

    private val _authState = MutableStateFlow<AuthState>(AuthState.Unknown)
    val authState: StateFlow<AuthState> = _authState.asStateFlow()
    private val _sessionEvents = MutableSharedFlow<SessionEvent>(extraBufferCapacity = 1)
    val sessionEvents: SharedFlow<SessionEvent> = _sessionEvents.asSharedFlow()
    private var postLoginDestination: PostLoginDestination? = null

    data class PostLoginDestination(val destinationId: Int, val arguments: android.os.Bundle?)

    fun init(context: Context) {
        appContext = context.applicationContext
        if (tokenStorage == null) {
            tokenStorage = SecureTokenStorage(context.applicationContext)
            checkInitialSession()
        }
    }

    // Visible for testing / dependency injection
    fun init(storage: SecureTokenStorage) {
        tokenStorage = storage
        checkInitialSession()
    }

    private fun checkInitialSession() {
        val storage = tokenStorage ?: return
        if (storage.hasValidTokens()) {
            val email = storage.getUserEmail().orEmpty()
            val name = storage.getUserName()
            _authState.value = AuthState.Authenticated(userEmail = email, userName = name)
        } else {
            _authState.value = AuthState.Unauthenticated
        }
    }

    fun hasValidSession(): Boolean {
        return tokenStorage?.hasValidTokens() == true
    }

    fun hasRefreshToken(): Boolean = !getRefreshToken().isNullOrBlank()

    /** Refresh near JWT expiry; opaque tokens remain on the reactive 401 refresh path. */
    fun shouldRefreshAccessTokenSoon(leewaySeconds: Long = 60): Boolean {
        val token = getAccessToken().orEmpty()
        if (token.isBlank()) return hasRefreshToken()
        val expiryMillis = runCatching {
            val payload = token.split('.').getOrNull(1) ?: return@runCatching null
            val decoded = Base64.decode(payload, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
            JSONObject(String(decoded, Charsets.UTF_8)).optLong("exp", 0L)
                .takeIf { it > 0L }?.times(1000L)
        }.getOrNull() ?: return false
        return expiryMillis <= System.currentTimeMillis() + leewaySeconds * 1000L
    }

    fun rememberPostLoginDestination(destinationId: Int, arguments: android.os.Bundle?) {
        postLoginDestination = PostLoginDestination(destinationId, arguments?.let { android.os.Bundle(it) })
    }

    fun consumePostLoginDestination(): PostLoginDestination? = postLoginDestination.also {
        postLoginDestination = null
    }

    fun getAccessToken(): String? = tokenStorage?.getAccessToken()

    fun getRefreshToken(): String? = tokenStorage?.getRefreshToken()

    fun getCurrentEmail(): String? = tokenStorage?.getUserEmail()

    fun getCurrentUserName(): String? = tokenStorage?.getUserName()

    fun getCurrentUserId(): String? = tokenStorage?.getUserId()

    fun applicationContext(): Context? = appContext

    fun storePendingFcmToken(token: String) = tokenStorage?.savePendingFcmToken(token)

    fun getPendingFcmToken(): String? = tokenStorage?.getPendingFcmToken()

    fun getDeviceId(): String? = tokenStorage?.getDeviceId()

    fun getRegisteredFcmToken(): String? = tokenStorage?.getRegisteredFcmToken()

    fun saveDeviceRegistration(deviceId: String, token: String) =
        tokenStorage?.saveDeviceRegistration(deviceId, token)

    fun clearDeviceRegistration() = tokenStorage?.clearDeviceRegistration()

    fun wasNotificationPermissionAsked(): Boolean =
        tokenStorage?.wasNotificationPermissionAsked() == true

    fun setNotificationPermissionAsked() = tokenStorage?.setNotificationPermissionAsked()

    fun saveSession(
        accessToken: String,
        refreshToken: String,
        userId: String? = null,
        email: String? = null,
        fullName: String? = null
    ) {
        val storage = tokenStorage ?: return
        storage.saveTokens(accessToken, refreshToken)
        if (email != null || fullName != null || userId != null) {
            storage.saveUserData(userId, email, fullName)
        }
        _authState.value = AuthState.Authenticated(
            userEmail = email ?: storage.getUserEmail().orEmpty(),
            userName = fullName ?: storage.getUserName()
        )
    }

    fun updateTokens(accessToken: String, refreshToken: String) {
        val storage = tokenStorage ?: return
        storage.saveTokens(accessToken, refreshToken)
        _authState.value = AuthState.Authenticated(
            userEmail = storage.getUserEmail().orEmpty(),
            userName = storage.getUserName()
        )
    }

    fun clearSession() {
        tokenStorage?.clear()
        postLoginDestination = null
        _authState.value = AuthState.Unauthenticated
    }

    fun notifySessionExpired() {
        tokenStorage?.clear()
        _authState.value = AuthState.SessionExpired
    }

    fun notifyRefreshUnavailable() {
        _sessionEvents.tryEmit(SessionEvent.RefreshTemporarilyUnavailable)
    }
}
