package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.auth.AuthSession
import com.fyp.basarattradeinvest.domain.model.auth.User
import com.fyp.basarattradeinvest.domain.model.auth.VerifyResetCodeResult

interface AuthRepository {

    suspend fun signup(
        email: String,
        password: String,
        fullName: String?
    ): Result<String>

    suspend fun verifyEmail(
        email: String,
        code: String
    ): Result<AuthSession>

    suspend fun resendVerification(
        email: String
    ): Result<String>

    suspend fun login(
        email: String,
        password: String
    ): Result<AuthSession>

    /**
     * Exchanges a Google OAuth ID token for a BASARAT session. Google-verified
     * accounts come back already verified, so no email-confirmation step follows.
     */
    suspend fun signInWithGoogle(
        idToken: String
    ): Result<AuthSession>

    suspend fun refresh(
        refreshToken: String
    ): Result<AuthSession>

    suspend fun logout(): Result<Unit>

    suspend fun forgotPassword(
        email: String
    ): Result<String>

    suspend fun verifyResetCode(
        email: String,
        code: String
    ): Result<VerifyResetCodeResult>

    suspend fun resetPassword(
        resetToken: String,
        newPassword: String,
        confirmPassword: String? = null
    ): Result<String>

    suspend fun changePassword(
        currentPassword: String,
        newPassword: String,
        confirmPassword: String? = null
    ): Result<String>

    fun isUserAuthenticated(): Boolean

    fun getCurrentUser(): User?

    fun clearLocalSession()
}
