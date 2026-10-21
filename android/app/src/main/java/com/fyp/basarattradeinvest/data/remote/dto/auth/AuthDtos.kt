package com.fyp.basarattradeinvest.data.remote.dto.auth

import com.fyp.basarattradeinvest.data.remote.dto.user.UserSummaryDto
import com.google.gson.annotations.SerializedName

// POST /api/v1/auth/signup Request
data class SignupRequest(
    @SerializedName("email")
    val email: String,

    @SerializedName("password")
    val password: String,

    @SerializedName("full_name")
    val fullName: String? = null
)

// POST /api/v1/auth/verify-email Request
data class VerifyEmailRequest(
    @SerializedName("email")
    val email: String,

    @SerializedName("code")
    val code: String
)

// POST /api/v1/auth/resend-verification Request
data class ResendVerificationRequest(
    @SerializedName("email")
    val email: String
)

// POST /api/v1/auth/login Request
data class LoginRequest(
    @SerializedName("email")
    val email: String,

    @SerializedName("password")
    val password: String
)

// POST /api/v1/auth/google Request
// The contract also accepts an optional Google `access_token` for avatar fallback, but
// Credential Manager only hands back the ID token, so it is never sent.
data class GoogleAuthRequest(
    @SerializedName("id_token")
    val idToken: String
)

// POST /api/v1/auth/refresh Request
data class RefreshRequest(
    @SerializedName("refresh_token")
    val refreshToken: String
)

// POST /api/v1/auth/logout Request
data class LogoutRequest(
    @SerializedName("refresh_token")
    val refreshToken: String
)

// POST /api/v1/auth/forgot-password Request
data class ForgotPasswordRequest(
    @SerializedName("email")
    val email: String
)

// POST /api/v1/auth/verify-reset-code Request
data class VerifyResetCodeRequest(
    @SerializedName("email")
    val email: String,

    @SerializedName("code")
    val code: String
)

// Response from POST /api/v1/auth/verify-reset-code (200 OK)
data class VerifyResetCodeResponse(
    @SerializedName("reset_token")
    val resetToken: String,

    @SerializedName("expires_in")
    val expiresIn: Int = 900,

    @SerializedName("token_type")
    val tokenType: String = "bearer",

    @SerializedName("message")
    val message: String? = null
)

// POST /api/v1/auth/reset-password Request
data class ResetPasswordRequest(
    @SerializedName("reset_token")
    val resetToken: String? = null,

    @SerializedName("email")
    val email: String? = null,

    @SerializedName("code")
    val code: String? = null,

    @SerializedName("new_password")
    val newPassword: String,

    @SerializedName("confirm_password")
    val confirmPassword: String? = null
)

// POST /api/v1/auth/change-password Request
data class ChangePasswordRequest(
    @SerializedName("current_password")
    val currentPassword: String,

    @SerializedName("new_password")
    val newPassword: String,

    @SerializedName("confirm_password")
    val confirmPassword: String? = null
)

// Response from /api/v1/auth/login, /api/v1/auth/google, /api/v1/auth/refresh, /api/v1/auth/verify-email
data class TokenResponse(
    @SerializedName("access_token")
    val accessToken: String,

    @SerializedName("refresh_token")
    val refreshToken: String,

    @SerializedName("token_type")
    val tokenType: String = "bearer",

    @SerializedName("user")
    val user: UserSummaryDto? = null
)

// Response from /api/v1/auth/signup, /resend-verification, /forgot-password, /reset-password, /change-password
data class MessageResponse(
    @SerializedName("message")
    val message: String
)

// OpenAPI 422 Validation Error Schemas
data class HTTPValidationError(
    @SerializedName("detail")
    val detail: List<ValidationErrorItem>? = null
)

data class ValidationErrorItem(
    @SerializedName("loc")
    val loc: List<Any>? = null,

    @SerializedName("msg")
    val msg: String? = null,

    @SerializedName("type")
    val type: String? = null
)
