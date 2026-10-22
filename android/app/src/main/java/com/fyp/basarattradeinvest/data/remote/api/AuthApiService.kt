package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.auth.ChangePasswordRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.ForgotPasswordRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.GoogleAuthRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.LoginRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.LogoutRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.MessageResponse
import com.fyp.basarattradeinvest.data.remote.dto.auth.RefreshRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.ResendVerificationRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.ResetPasswordRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.SignupRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.TokenResponse
import com.fyp.basarattradeinvest.data.remote.dto.auth.VerifyEmailRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.VerifyResetCodeRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.VerifyResetCodeResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

/**
 * Retrofit service definition for BASARAT Authentication endpoints.
 * Defined strictly according to the OpenAPI contract served by the backend at
 * /api/v1/openapi.json (see NetworkClient for the host).
 */
interface AuthApiService {

    @POST("api/v1/auth/signup")
    suspend fun signup(
        @Body request: SignupRequest
    ): Response<MessageResponse>

    @POST("api/v1/auth/verify-email")
    suspend fun verifyEmail(
        @Body request: VerifyEmailRequest
    ): Response<TokenResponse>

    @POST("api/v1/auth/resend-verification")
    suspend fun resendVerification(
        @Body request: ResendVerificationRequest
    ): Response<MessageResponse>

    @POST("api/v1/auth/login")
    suspend fun login(
        @Body request: LoginRequest
    ): Response<TokenResponse>

    @POST("api/v1/auth/google")
    suspend fun continueWithGoogle(
        @Body request: GoogleAuthRequest
    ): Response<TokenResponse>

    @POST("api/v1/auth/refresh")
    suspend fun refresh(
        @Body request: RefreshRequest
    ): Response<TokenResponse>

    @POST("api/v1/auth/logout")
    suspend fun logout(
        @Body request: LogoutRequest
    ): Response<Unit>

    @POST("api/v1/auth/forgot-password")
    suspend fun forgotPassword(
        @Body request: ForgotPasswordRequest
    ): Response<MessageResponse>

    @POST("api/v1/auth/verify-reset-code")
    suspend fun verifyResetCode(
        @Body request: VerifyResetCodeRequest
    ): Response<VerifyResetCodeResponse>

    @POST("api/v1/auth/reset-password")
    suspend fun resetPassword(
        @Body request: ResetPasswordRequest
    ): Response<MessageResponse>

    @POST("api/v1/auth/change-password")
    suspend fun changePassword(
        @Body request: ChangePasswordRequest
    ): Response<MessageResponse>
}
