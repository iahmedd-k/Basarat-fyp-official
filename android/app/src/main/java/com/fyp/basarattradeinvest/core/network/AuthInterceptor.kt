package com.fyp.basarattradeinvest.core.network

import com.fyp.basarattradeinvest.core.session.SessionManager
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor : Interceptor {

    companion object {
        private val UNAUTHENTICATED_PATHS = listOf(
            "/api/v1/auth/login",
            "/api/v1/auth/signup",
            "/api/v1/auth/verify-email",
            "/api/v1/auth/resend-verification",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/verify-reset-code",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/refresh"
        )
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val path = request.url.encodedPath

        val isUnauthenticated = UNAUTHENTICATED_PATHS.any { path.endsWith(it) }

        val requestBuilder = request.newBuilder()
        if (request.header("Accept") == null) {
            requestBuilder.header("Accept", "application/json")
        }

        val isPublicMarketWebSocket = path == "/api/v1/ws/market"
        if (!isUnauthenticated && !isPublicMarketWebSocket) {
            val token = SessionManager.getAccessToken()
            if (!token.isNullOrBlank() && request.header("Authorization") == null) {
                requestBuilder.header("Authorization", "Bearer $token")
            }
        }

        return chain.proceed(requestBuilder.build())
    }
}
