package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.model.auth.AuthSession
import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class GoogleSignInUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(idToken: String): Result<AuthSession> {
        val token = idToken.trim()
        if (token.isEmpty()) {
            return Result.failure(IllegalArgumentException("Google ID token cannot be empty"))
        }
        return repository.signInWithGoogle(token)
    }
}
