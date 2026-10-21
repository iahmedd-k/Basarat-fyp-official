package com.fyp.basarattradeinvest.data.remote.dto.auth

/**
 * AuthPayloads
 *
 * Centralized registry of pre-constructed payloads and factories for all 7 BASARAT backend
 * authentication endpoints. Provides ready-to-use payloads with valid defaults so developers
 * and automated test suites do not need to explicitly build or specify request bodies.
 */
object AuthPayloads {

    // Default test credentials
    const val DEFAULT_EMAIL = "test.trader@basarat.pk"
    const val DEFAULT_PASSWORD = "Password123!"
    const val DEFAULT_FULL_NAME = "Basarat Demo Trader"
    const val DEFAULT_NEW_PASSWORD = "NewPassword123!"
    const val DUMMY_REFRESH_TOKEN = "dummy_refresh_token_for_validation"
    const val DUMMY_RESET_TOKEN = "dummy_reset_token_for_validation"

    // 1. SIGNUP PAYLOADS (POST /api/v1/auth/signup)
    fun signupPayload(
        email: String = "trader_${System.currentTimeMillis()}@basarat.pk",
        password: String = DEFAULT_PASSWORD,
        fullName: String? = DEFAULT_FULL_NAME
    ) = SignupRequest(
        email = email,
        password = password,
        fullName = fullName
    )

    val VALID_SIGNUP by lazy {
        SignupRequest(
            email = "automated_test_${System.currentTimeMillis()}@basarat.pk",
            password = DEFAULT_PASSWORD,
            fullName = "Automated Test User"
        )
    }

    val MINIMAL_SIGNUP = SignupRequest(
        email = "minimal_trader@basarat.pk",
        password = DEFAULT_PASSWORD,
        fullName = null
    )

    val INVALID_SHORT_PASSWORD_SIGNUP = SignupRequest(
        email = DEFAULT_EMAIL,
        password = "short", // Fails minLength 8 constraint
        fullName = DEFAULT_FULL_NAME
    )

    val INVALID_EMAIL_SIGNUP = SignupRequest(
        email = "not-an-email",
        password = DEFAULT_PASSWORD,
        fullName = DEFAULT_FULL_NAME
    )

    // 2. LOGIN PAYLOADS (POST /api/v1/auth/login)
    fun loginPayload(
        email: String = DEFAULT_EMAIL,
        password: String = DEFAULT_PASSWORD
    ) = LoginRequest(
        email = email,
        password = password
    )

    val VALID_LOGIN = LoginRequest(
        email = DEFAULT_EMAIL,
        password = DEFAULT_PASSWORD
    )

    val WRONG_PASSWORD_LOGIN = LoginRequest(
        email = DEFAULT_EMAIL,
        password = "WrongPassword999!"
    )

    val INVALID_EMAIL_LOGIN = LoginRequest(
        email = "invalid_user@nonexistent.domain",
        password = DEFAULT_PASSWORD
    )

    // 3. REFRESH PAYLOADS (POST /api/v1/auth/refresh)
    fun refreshPayload(
        refreshToken: String = DUMMY_REFRESH_TOKEN
    ) = RefreshRequest(
        refreshToken = refreshToken
    )

    val DUMMY_REFRESH = RefreshRequest(refreshToken = DUMMY_REFRESH_TOKEN)

    // 4. LOGOUT PAYLOADS (POST /api/v1/auth/logout)
    fun logoutPayload(
        refreshToken: String = DUMMY_REFRESH_TOKEN
    ) = LogoutRequest(
        refreshToken = refreshToken
    )

    val DUMMY_LOGOUT = LogoutRequest(refreshToken = DUMMY_REFRESH_TOKEN)

    // 5. FORGOT PASSWORD PAYLOADS (POST /api/v1/auth/forgot-password)
    fun forgotPasswordPayload(
        email: String = DEFAULT_EMAIL
    ) = ForgotPasswordRequest(
        email = email
    )

    val VALID_FORGOT_PASSWORD = ForgotPasswordRequest(email = DEFAULT_EMAIL)
    val INVALID_EMAIL_FORGOT_PASSWORD = ForgotPasswordRequest(email = "invalid-email-format")

    // 6. RESET PASSWORD PAYLOADS (POST /api/v1/auth/reset-password)
    fun resetPasswordPayload(
        token: String = DUMMY_RESET_TOKEN,
        newPassword: String = DEFAULT_NEW_PASSWORD
    ) = ResetPasswordRequest(
        resetToken = token,
        newPassword = newPassword
    )

    val DUMMY_RESET_PASSWORD = ResetPasswordRequest(
        resetToken = DUMMY_RESET_TOKEN,
        newPassword = DEFAULT_NEW_PASSWORD
    )

    // 7. CHANGE PASSWORD PAYLOADS (POST /api/v1/auth/change-password)
    fun changePasswordPayload(
        currentPassword: String = DEFAULT_PASSWORD,
        newPassword: String = DEFAULT_NEW_PASSWORD
    ) = ChangePasswordRequest(
        currentPassword = currentPassword,
        newPassword = newPassword
    )

    val VALID_CHANGE_PASSWORD = ChangePasswordRequest(
        currentPassword = DEFAULT_PASSWORD,
        newPassword = DEFAULT_NEW_PASSWORD
    )

    val SHORT_NEW_PASSWORD_CHANGE = ChangePasswordRequest(
        currentPassword = DEFAULT_PASSWORD,
        newPassword = "short" // Fails minLength 8
    )
}
