package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.remote.dto.auth.AuthPayloads
import com.fyp.basarattradeinvest.data.remote.dto.auth.ResendVerificationRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.VerifyEmailRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.VerifyResetCodeRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

data class EndpointTestResult(
    val endpoint: String,
    val httpMethod: String,
    val statusCode: Int,
    val isSuccessful: Boolean,
    val responseSummary: String
)

class AuthPayloadRunner(
    private val apiService: AuthApiService
) {

    suspend fun testSignup(
        email: String = AuthPayloads.DEFAULT_EMAIL,
        password: String = AuthPayloads.DEFAULT_PASSWORD,
        fullName: String = AuthPayloads.DEFAULT_FULL_NAME
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val payload = AuthPayloads.signupPayload(email, password, fullName)
        val response = apiService.signup(payload)
        EndpointTestResult(
            endpoint = "/api/v1/auth/signup",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                response.body()?.message ?: "201 Created"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testVerifyEmail(
        email: String = AuthPayloads.DEFAULT_EMAIL,
        code: String = "123456"
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val response = apiService.verifyEmail(VerifyEmailRequest(email, code))
        EndpointTestResult(
            endpoint = "/api/v1/auth/verify-email",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                "User verified, tokens received"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testResendVerification(
        email: String = AuthPayloads.DEFAULT_EMAIL
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val response = apiService.resendVerification(ResendVerificationRequest(email))
        EndpointTestResult(
            endpoint = "/api/v1/auth/resend-verification",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                response.body()?.message ?: "Verification code resent"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testLogin(
        email: String = AuthPayloads.DEFAULT_EMAIL,
        password: String = AuthPayloads.DEFAULT_PASSWORD
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val payload = AuthPayloads.loginPayload(email, password)
        val response = apiService.login(payload)
        EndpointTestResult(
            endpoint = "/api/v1/auth/login",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                "User: ${response.body()?.user?.email}, Access token granted"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testRefresh(
        refreshToken: String = AuthPayloads.DUMMY_REFRESH_TOKEN
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val payload = AuthPayloads.refreshPayload(refreshToken)
        val response = apiService.refresh(payload)
        EndpointTestResult(
            endpoint = "/api/v1/auth/refresh",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                "New access token received"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testLogout(
        refreshToken: String = AuthPayloads.DUMMY_REFRESH_TOKEN
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val payload = AuthPayloads.logoutPayload(refreshToken)
        val response = apiService.logout(payload)
        EndpointTestResult(
            endpoint = "/api/v1/auth/logout",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) "Logged out successfully (204 No Content)" else NetworkErrorParser.parseError(response)
        )
    }

    suspend fun testForgotPassword(
        email: String = AuthPayloads.DEFAULT_EMAIL
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val payload = AuthPayloads.forgotPasswordPayload(email)
        val response = apiService.forgotPassword(payload)
        EndpointTestResult(
            endpoint = "/api/v1/auth/forgot-password",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                response.body()?.message ?: "Reset code sent"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testVerifyResetCode(
        email: String = AuthPayloads.DEFAULT_EMAIL,
        code: String = "123456"
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val response = apiService.verifyResetCode(VerifyResetCodeRequest(email, code))
        EndpointTestResult(
            endpoint = "/api/v1/auth/verify-reset-code",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                "Reset token grant received"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testResetPassword(
        token: String = AuthPayloads.DUMMY_RESET_TOKEN,
        newPassword: String = AuthPayloads.DEFAULT_NEW_PASSWORD
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val payload = AuthPayloads.resetPasswordPayload(token, newPassword)
        val response = apiService.resetPassword(payload)
        EndpointTestResult(
            endpoint = "/api/v1/auth/reset-password",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                response.body()?.message ?: "Password reset successful"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun testChangePassword(
        currentPassword: String = AuthPayloads.DEFAULT_PASSWORD,
        newPassword: String = AuthPayloads.DEFAULT_NEW_PASSWORD
    ): EndpointTestResult = withContext(Dispatchers.IO) {
        val payload = AuthPayloads.changePasswordPayload(currentPassword, newPassword)
        val response = apiService.changePassword(payload)
        EndpointTestResult(
            endpoint = "/api/v1/auth/change-password",
            httpMethod = "POST",
            statusCode = response.code(),
            isSuccessful = response.isSuccessful,
            responseSummary = if (response.isSuccessful) {
                response.body()?.message ?: "Password changed successfully"
            } else {
                NetworkErrorParser.parseError(response)
            }
        )
    }

    suspend fun runAllEndpointTests(): List<EndpointTestResult> {
        val results = mutableListOf<EndpointTestResult>()
        results.add(testSignup())
        results.add(testVerifyEmail())
        results.add(testResendVerification())
        results.add(testLogin())
        results.add(testRefresh())
        results.add(testLogout())
        results.add(testForgotPassword())
        results.add(testVerifyResetCode())
        results.add(testResetPassword())
        results.add(testChangePassword())
        return results
    }
}
