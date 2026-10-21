package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.model.auth.AuthSession
import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class VerifyEmailUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(email: String, code: String): Result<AuthSession> {
        val trimmedEmail = email.trim()
        val trimmedCode = code.trim()

        if (trimmedEmail.isEmpty()) {
            return Result.failure(IllegalArgumentException("Email cannot be empty"))
        }
        if (trimmedCode.length != 6) {
            return Result.failure(IllegalArgumentException("Verification code must be 6 digits"))
        }
        return repository.verifyEmail(trimmedEmail, trimmedCode)
    }
}
