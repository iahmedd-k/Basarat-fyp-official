package com.fyp.basarattradeinvest.auth

import com.fyp.basarattradeinvest.data.remote.api.AuthApiService
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
import com.fyp.basarattradeinvest.data.remote.dto.user.UserSummaryDto
import com.fyp.basarattradeinvest.data.repository.AuthRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.auth.ChangePasswordUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.ForgotPasswordUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.GoogleSignInUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.LoginUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.ResendVerificationUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.ResetPasswordUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.SignUpUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.VerifyEmailUseCase
import com.fyp.basarattradeinvest.domain.usecase.auth.VerifyResetCodeUseCase
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class AuthModuleUnitTest {

    // Fake AuthApiService implementation for isolated, deterministic unit testing
    private val fakeApiService = object : AuthApiService {
        var shouldFailLogin = false
        var shouldFailSignup = false
        var shouldFailVerifyEmail = false
        var shouldFailVerifyResetCode = false
        var shouldFailGoogle = false
        var lastGoogleIdToken: String? = null

        override suspend fun signup(request: SignupRequest): Response<MessageResponse> {
            return if (shouldFailSignup) {
                val errorBody = "{\"detail\":\"Email already registered\"}"
                    .toResponseBody("application/json".toMediaType())
                Response.error(400, errorBody)
            } else {
                Response.success(MessageResponse("Account created. Please check your email for the verification code."))
            }
        }

        override suspend fun verifyEmail(request: VerifyEmailRequest): Response<TokenResponse> {
            return if (shouldFailVerifyEmail || request.code != "123456") {
                val errorBody = "{\"success\":false,\"error\":{\"code\":\"BAD_REQUEST\",\"message\":\"Invalid email or code.\"}}"
                    .toResponseBody("application/json".toMediaType())
                Response.error(400, errorBody)
            } else {
                val tokenResponse = TokenResponse(
                    accessToken = "mock_verified_access_token",
                    refreshToken = "mock_verified_refresh_token",
                    tokenType = "bearer",
                    user = UserSummaryDto(
                        id = "user_456",
                        email = request.email,
                        username = "verified_user",
                        fullName = "Verified User"
                    )
                )
                Response.success(tokenResponse)
            }
        }

        override suspend fun resendVerification(request: ResendVerificationRequest): Response<MessageResponse> {
            return Response.success(MessageResponse("Verification code sent to your email."))
        }

        override suspend fun login(request: LoginRequest): Response<TokenResponse> {
            return if (shouldFailLogin) {
                val errorBody = "{\"detail\":\"Incorrect email or password\"}"
                    .toResponseBody("application/json".toMediaType())
                Response.error(401, errorBody)
            } else {
                val tokenResponse = TokenResponse(
                    accessToken = "mock_jwt_access_token",
                    refreshToken = "mock_jwt_refresh_token",
                    tokenType = "bearer",
                    user = UserSummaryDto(
                        id = "user_123",
                        email = request.email,
                        username = "test_user",
                        fullName = "Test User"
                    )
                )
                Response.success(tokenResponse)
            }
        }

        override suspend fun continueWithGoogle(request: GoogleAuthRequest): Response<TokenResponse> {
            lastGoogleIdToken = request.idToken
            return if (shouldFailGoogle) {
                val errorBody = "{\"detail\":\"Invalid Google token\"}"
                    .toResponseBody("application/json".toMediaType())
                Response.error(401, errorBody)
            } else {
                val tokenResponse = TokenResponse(
                    accessToken = "mock_google_access_token",
                    refreshToken = "mock_google_refresh_token",
                    tokenType = "bearer",
                    user = UserSummaryDto(
                        id = "user_789",
                        email = "google.user@basarat.pk",
                        username = "google_user",
                        fullName = "Google User"
                    )
                )
                Response.success(tokenResponse)
            }
        }

        override suspend fun refresh(request: RefreshRequest): Response<TokenResponse> {            val tokenResponse = TokenResponse(
                accessToken = "new_mock_jwt_access_token",
                refreshToken = "new_mock_jwt_refresh_token",
                tokenType = "bearer"
            )
            return Response.success(tokenResponse)
        }

        override suspend fun logout(request: LogoutRequest): Response<Unit> {
            return Response.success(204, Unit)
        }

        override suspend fun forgotPassword(request: ForgotPasswordRequest): Response<MessageResponse> {
            return Response.success(MessageResponse("If the email exists, a 6-digit reset code has been sent."))
        }

        override suspend fun verifyResetCode(request: VerifyResetCodeRequest): Response<VerifyResetCodeResponse> {
            return if (shouldFailVerifyResetCode || request.code != "123456") {
                val errorBody = "{\"success\":false,\"error\":{\"code\":\"BAD_REQUEST\",\"message\":\"Invalid email or reset code.\"}}"
                    .toResponseBody("application/json".toMediaType())
                Response.error(400, errorBody)
            } else {
                Response.success(
                    VerifyResetCodeResponse(
                        resetToken = "mock_grant_reset_token",
                        expiresIn = 900,
                        tokenType = "bearer",
                        message = "Code verified successfully"
                    )
                )
            }
        }

        override suspend fun resetPassword(request: ResetPasswordRequest): Response<MessageResponse> {
            return Response.success(MessageResponse("Password reset successfully. Please log in."))
        }

        override suspend fun changePassword(request: ChangePasswordRequest): Response<MessageResponse> {
            return Response.success(MessageResponse("Password changed successfully."))
        }
    }

    private val authRepository = AuthRepositoryImpl(fakeApiService)

    @Test
    fun testLoginSuccess() = runBlocking {
        fakeApiService.shouldFailLogin = false
        val result = authRepository.login("test@basarat.pk", "Password123!")

        assertTrue(result.isSuccess)
        val session = result.getOrNull()
        assertNotNull(session)
        assertEquals("mock_jwt_access_token", session?.accessToken)
        assertEquals("test@basarat.pk", session?.user?.email)
    }

    @Test
    fun testLoginFailure() = runBlocking {
        fakeApiService.shouldFailLogin = true
        val result = authRepository.login("test@basarat.pk", "WrongPassword")

        assertTrue(result.isFailure)
        val errorMsg = result.exceptionOrNull()?.message
        assertTrue(errorMsg?.contains("Incorrect email or password") == true)
    }

    @Test
    fun testSignupSuccess() = runBlocking {
        fakeApiService.shouldFailSignup = false
        val result = authRepository.signup("newuser@basarat.pk", "Password123!", "New User")

        assertTrue(result.isSuccess)
        assertEquals("Account created. Please check your email for the verification code.", result.getOrNull())
    }

    @Test
    fun testSignupFailureDuplicateEmail() = runBlocking {
        fakeApiService.shouldFailSignup = true
        val result = authRepository.signup("duplicate@basarat.pk", "Password123!", "Duplicate User")

        assertTrue(result.isFailure)
        val errorMsg = result.exceptionOrNull()?.message
        assertTrue(errorMsg?.contains("Email already registered") == true)
    }

    @Test
    fun testVerifyEmailSuccess() = runBlocking {
        fakeApiService.shouldFailVerifyEmail = false
        val result = authRepository.verifyEmail("newuser@basarat.pk", "123456")

        assertTrue(result.isSuccess)
        val session = result.getOrNull()
        assertNotNull(session)
        assertEquals("mock_verified_access_token", session?.accessToken)
        assertEquals("newuser@basarat.pk", session?.user?.email)
    }

    @Test
    fun testVerifyEmailFailureInvalidCode() = runBlocking {
        fakeApiService.shouldFailVerifyEmail = true
        val result = authRepository.verifyEmail("newuser@basarat.pk", "000000")

        assertTrue(result.isFailure)
        val errorMsg = result.exceptionOrNull()?.message
        assertTrue(errorMsg?.contains("Invalid email or code") == true)
    }

    @Test
    fun testResendVerificationSuccess() = runBlocking {
        val result = authRepository.resendVerification("newuser@basarat.pk")
        assertTrue(result.isSuccess)
        assertEquals("Verification code sent to your email.", result.getOrNull())
    }

    @Test
    fun testForgotPasswordSuccess() = runBlocking {
        val result = authRepository.forgotPassword("user@basarat.pk")
        assertTrue(result.isSuccess)
        assertEquals("If the email exists, a 6-digit reset code has been sent.", result.getOrNull())
    }

    @Test
    fun testVerifyResetCodeSuccess() = runBlocking {
        fakeApiService.shouldFailVerifyResetCode = false
        val result = authRepository.verifyResetCode("user@basarat.pk", "123456")

        assertTrue(result.isSuccess)
        val res = result.getOrNull()
        assertNotNull(res)
        assertEquals("mock_grant_reset_token", res?.resetToken)
    }

    @Test
    fun testResetPasswordSuccess() = runBlocking {
        val result = authRepository.resetPassword("mock_grant_reset_token", "NewPassword123!", "NewPassword123!")
        assertTrue(result.isSuccess)
        assertEquals("Password reset successfully. Please log in.", result.getOrNull())
    }

    @Test
    fun testChangePasswordSuccess() = runBlocking {
        val result = authRepository.changePassword("OldPassword123!", "NewPassword123!", "NewPassword123!")
        assertTrue(result.isSuccess)
        assertEquals("Password changed successfully.", result.getOrNull())
    }

    @Test
    fun testGoogleSignInSuccess() = runBlocking {
        fakeApiService.shouldFailGoogle = false
        val result = authRepository.signInWithGoogle("mock_google_id_token")

        assertTrue(result.isSuccess)
        val session = result.getOrNull()
        assertNotNull(session)
        assertEquals("mock_google_access_token", session?.accessToken)
        assertEquals("mock_google_refresh_token", session?.refreshToken)
        assertEquals("google.user@basarat.pk", session?.user?.email)
        // The ID token must reach the backend verbatim in `id_token`.
        assertEquals("mock_google_id_token", fakeApiService.lastGoogleIdToken)
    }

    @Test
    fun testGoogleSignInFailure() = runBlocking {
        fakeApiService.shouldFailGoogle = true
        val result = authRepository.signInWithGoogle("mock_google_id_token")

        assertTrue(result.isFailure)
        val errorMsg = result.exceptionOrNull()?.message
        assertTrue(errorMsg?.contains("Invalid Google token") == true)
    }

    @Test
    fun testGoogleSignInUseCaseRejectsBlankToken() = runBlocking {
        val googleSignInUseCase = GoogleSignInUseCase(authRepository)
        val result = googleSignInUseCase("   ")

        assertTrue(result.isFailure)
        // Guarded before the network call, so the endpoint was never touched.
        assertNull(fakeApiService.lastGoogleIdToken)
    }

    @Test
    fun testUseCasesValidation() = runBlocking {
        val verifyEmailUseCase = VerifyEmailUseCase(authRepository)
        val invalidCodeResult = verifyEmailUseCase("test@example.com", "12")
        assertTrue(invalidCodeResult.isFailure)

        val verifyResetCodeUseCase = VerifyResetCodeUseCase(authRepository)
        val emptyEmailReset = verifyResetCodeUseCase("", "123456")
        assertTrue(emptyEmailReset.isFailure)

        val resetPasswordUseCase = ResetPasswordUseCase(authRepository)
        val mismatchPassword = resetPasswordUseCase("token", "Pass12345!", "DifferentPass123!")
        assertTrue(mismatchPassword.isFailure)

        val changePasswordUseCase = ChangePasswordUseCase(authRepository)
        val mismatchChange = changePasswordUseCase("Current123!", "NewPass123!", "Mismatch123!")
        assertTrue(mismatchChange.isFailure)
    }
}
