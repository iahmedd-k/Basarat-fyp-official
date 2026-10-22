package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.model.auth.VerifyResetCodeResult
import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class VerifyResetCodeUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(email: String, code: String): Result<VerifyResetCodeResult> {
        val trimmedEmail = email.trim()
        val trimmedCode = code.trim()

        if (trimmedEmail.isEmpty()) {
            return Result.failure(IllegalArgumentException("Email cannot be empty"))
        }
        if (trimmedCode.length != 6) {
            return Result.failure(IllegalArgumentException("Reset code must be 6 digits"))
        }
        return repository.verifyResetCode(trimmedEmail, trimmedCode)
    }
}
