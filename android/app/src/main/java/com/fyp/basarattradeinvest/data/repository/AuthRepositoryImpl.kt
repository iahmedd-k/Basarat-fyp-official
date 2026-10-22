package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.core.session.RefreshTokenFailure
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.core.notifications.DeviceRegistrationScheduler
import com.fyp.basarattradeinvest.core.notifications.NotificationBadgeState
import com.fyp.basarattradeinvest.data.remote.api.AuthApiService
import com.fyp.basarattradeinvest.data.remote.dto.auth.ChangePasswordRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.ForgotPasswordRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.GoogleAuthRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.LoginRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.LogoutRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.RefreshRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.ResendVerificationRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.ResetPasswordRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.SignupRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.TokenResponse
import com.fyp.basarattradeinvest.data.remote.dto.auth.VerifyEmailRequest
import com.fyp.basarattradeinvest.data.remote.dto.auth.VerifyResetCodeRequest
import com.fyp.basarattradeinvest.domain.model.auth.AuthSession
import com.fyp.basarattradeinvest.domain.model.auth.User
import com.fyp.basarattradeinvest.domain.model.auth.VerifyResetCodeResult
import com.fyp.basarattradeinvest.domain.repository.AuthRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class AuthRepositoryImpl(
    private val apiService: AuthApiService = NetworkClient.authApiService,
    private val devicesRepository: com.fyp.basarattradeinvest.domain.repository.DevicesRepository = DevicesRepositoryImpl()
) : AuthRepository {

    override suspend fun signup(
        email: String,
        password: String,
        fullName: String?
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.signup(
                SignupRequest(
                    email = email,
                    password = password,
                    fullName = fullName
                )
            )
            if (response.isSuccessful) {
                val message = response.body()?.message ?: "Account created. Please check your email for the verification code."
                Result.success(message)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun verifyEmail(
        email: String,
        code: String
    ): Result<AuthSession> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.verifyEmail(
                VerifyEmailRequest(
                    email = email,
                    code = code
                )
            )
            if (response.isSuccessful) {
                val body = response.body() ?: return@withContext Result.failure(Exception("Empty verification response from server"))
                
                SessionManager.saveSession(
                    accessToken = body.accessToken,
                    refreshToken = body.refreshToken,
                    userId = body.user?.id?.toString(),
                    email = body.user?.email ?: email,
                    fullName = body.user?.fullName
                )

                val user = body.user?.let {
                    User(
                        id = it.id.toString(),
                        email = it.email,
                        username = it.username,
                        fullName = it.fullName
                    )
                } ?: User(id = "", email = email)

                Result.success(
                    AuthSession(
                        accessToken = body.accessToken,
                        refreshToken = body.refreshToken,
                        tokenType = body.tokenType,
                        user = user
                    )
                )
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun resendVerification(
        email: String
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.resendVerification(
                ResendVerificationRequest(email = email)
            )
            if (response.isSuccessful) {
                val message = response.body()?.message ?: "Verification code sent to your email."
                Result.success(message)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun login(
        email: String,
        password: String
    ): Result<AuthSession> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.login(
                LoginRequest(
                    email = email,
                    password = password
                )
            )
            if (response.isSuccessful) {
                val body = response.body() ?: return@withContext Result.failure(Exception("Empty login response from server"))
                persistSession(body, fallbackEmail = email)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun signInWithGoogle(
        idToken: String
    ): Result<AuthSession> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.continueWithGoogle(GoogleAuthRequest(idToken = idToken))
            if (response.isSuccessful) {
                val body = response.body()
                    ?: return@withContext Result.failure(Exception("Empty Google sign-in response from server"))
                persistSession(body, fallbackEmail = null)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Shared tail of every token-returning sign-in: persist the session and hand back
     * the same [AuthSession] shape the email login produces.
     */
    private fun persistSession(body: TokenResponse, fallbackEmail: String?): Result<AuthSession> {
        val user = body.user?.let {
            User(
                id = it.id.toString(),
                email = it.email,
                username = it.username,
                fullName = it.fullName
            )
        } ?: fallbackEmail?.let { User(id = "", email = it) }
            ?: return Result.failure(Exception("Server did not return an account for this sign-in"))

        SessionManager.saveSession(
            accessToken = body.accessToken,
            refreshToken = body.refreshToken,
            userId = body.user?.id?.toString(),
            email = user.email,
            fullName = body.user?.fullName
        )

        return Result.success(
            AuthSession(
                accessToken = body.accessToken,
                refreshToken = body.refreshToken,
                tokenType = body.tokenType,
                user = user
            )
        )
    }

    override suspend fun refresh(refreshToken: String): Result<AuthSession> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.refresh(RefreshRequest(refreshToken))
            if (response.isSuccessful) {
                val body = response.body() ?: return@withContext Result.failure(
                    RefreshTokenFailure("Empty refresh response from server")
                )
                
                SessionManager.updateTokens(body.accessToken, body.refreshToken)
                
                val user = body.user?.let {
                    User(
                        id = it.id.toString(),
                        email = it.email,
                        username = it.username,
                        fullName = it.fullName
                    )
                }

                Result.success(
                    AuthSession(
                        accessToken = body.accessToken,
                        refreshToken = body.refreshToken,
                        tokenType = body.tokenType,
                        user = user
                    )
                )
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(RefreshTokenFailure(error, statusCode = response.code()))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            Result.failure(RefreshTokenFailure(e.message ?: "Unable to reach the refresh service", cause = e))
        }
    }

    override suspend fun logout(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            SessionManager.applicationContext()?.let(DeviceRegistrationScheduler::cancel)
            val deviceId = SessionManager.getDeviceId()
            if (!deviceId.isNullOrBlank()) {
                runCatching { devicesRepository.unregisterDevice(deviceId) }
            }
            SessionManager.clearDeviceRegistration()
            NotificationBadgeState.reset()

            val refreshToken = SessionManager.getRefreshToken()
            if (!refreshToken.isNullOrBlank()) {
                try {
                    apiService.logout(LogoutRequest(refreshToken))
                } catch (_: Exception) {
                    // Safe graceful degradation: even if server call fails, local session is cleared
                }
            }
            SessionManager.clearSession()
            Result.success(Unit)
        } catch (e: Exception) {
            SessionManager.clearSession()
            NotificationBadgeState.reset()
            Result.success(Unit)
        }
    }

    override suspend fun forgotPassword(email: String): Result<String> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.forgotPassword(ForgotPasswordRequest(email))
            if (response.isSuccessful) {
                val msg = response.body()?.message ?: "If the email exists, a 6-digit reset code has been sent."
                Result.success(msg)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun verifyResetCode(
        email: String,
        code: String
    ): Result<VerifyResetCodeResult> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.verifyResetCode(
                VerifyResetCodeRequest(
                    email = email,
                    code = code
                )
            )
            if (response.isSuccessful) {
                val body = response.body() ?: return@withContext Result.failure(Exception("Empty response from reset code verification"))
                Result.success(
                    VerifyResetCodeResult(
                        resetToken = body.resetToken,
                        expiresIn = body.expiresIn,
                        tokenType = body.tokenType,
                        message = body.message
                    )
                )
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun resetPassword(
        resetToken: String,
        newPassword: String,
        confirmPassword: String?
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.resetPassword(
                ResetPasswordRequest(
                    resetToken = resetToken,
                    newPassword = newPassword,
                    confirmPassword = confirmPassword ?: newPassword
                )
            )
            if (response.isSuccessful) {
                val msg = response.body()?.message ?: "Password reset successfully. Please log in."
                Result.success(msg)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun changePassword(
        currentPassword: String,
        newPassword: String,
        confirmPassword: String?
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.changePassword(
                ChangePasswordRequest(
                    currentPassword = currentPassword,
                    newPassword = newPassword,
                    confirmPassword = confirmPassword ?: newPassword
                )
            )
            if (response.isSuccessful) {
                val msg = response.body()?.message ?: "Password changed successfully."
                Result.success(msg)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override fun isUserAuthenticated(): Boolean {
        return SessionManager.hasValidSession()
    }

    override fun getCurrentUser(): User? {
        val email = SessionManager.getCurrentEmail() ?: return null
        return User(
            id = SessionManager.getCurrentUserId().orEmpty(),
            email = email,
            fullName = SessionManager.getCurrentUserName()
        )
    }

    override fun clearLocalSession() {
        SessionManager.clearSession()
    }
}
