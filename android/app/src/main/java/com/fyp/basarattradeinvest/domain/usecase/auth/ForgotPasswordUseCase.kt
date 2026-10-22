package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class ForgotPasswordUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(email: String): Result<String> {
        val trimmed = email.trim()
        if (trimmed.isEmpty()) {
            return Result.failure(IllegalArgumentException("Email cannot be empty"))
        }
        return repository.forgotPassword(trimmed)
    }
}
