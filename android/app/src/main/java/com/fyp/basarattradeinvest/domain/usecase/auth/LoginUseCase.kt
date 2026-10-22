package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.model.auth.AuthSession
import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class LoginUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(email: String, password: String): Result<AuthSession> {
        val trimmedEmail = email.trim()
        if (trimmedEmail.isEmpty()) {
            return Result.failure(IllegalArgumentException("Email cannot be empty"))
        }
        if (password.isEmpty()) {
            return Result.failure(IllegalArgumentException("Password cannot be empty"))
        }
        return repository.login(trimmedEmail, password)
    }
}
