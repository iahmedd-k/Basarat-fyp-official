package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class ChangePasswordUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(
        currentPassword: String,
        newPassword: String,
        confirmPassword: String? = null
    ): Result<String> {
        if (currentPassword.isEmpty()) {
            return Result.failure(IllegalArgumentException("Current password cannot be empty"))
        }
        if (newPassword.length < 8) {
            return Result.failure(IllegalArgumentException("New password must be at least 8 characters"))
        }
        if (confirmPassword != null && newPassword != confirmPassword) {
            return Result.failure(IllegalArgumentException("New passwords do not match"))
        }
        return repository.changePassword(currentPassword, newPassword, confirmPassword)
    }
}
