package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class ResetPasswordUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(
        resetToken: String,
        newPassword: String,
        confirmPassword: String? = null
    ): Result<String> {
        val trimmedToken = resetToken.trim()
        if (trimmedToken.isEmpty()) {
            return Result.failure(IllegalArgumentException("Reset token grant is missing"))
        }
        if (newPassword.length < 8) {
            return Result.failure(IllegalArgumentException("New password must be at least 8 characters"))
        }
        if (confirmPassword != null && newPassword != confirmPassword) {
            return Result.failure(IllegalArgumentException("Passwords do not match"))
        }
        return repository.resetPassword(trimmedToken, newPassword, confirmPassword)
    }
}
