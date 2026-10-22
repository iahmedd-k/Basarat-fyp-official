package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.model.auth.AuthSession
import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class RefreshTokenUseCase(private val repository: AuthRepository) {
    suspend operator fun invoke(refreshToken: String): Result<AuthSession> {
        if (refreshToken.isBlank()) {
            return Result.failure(IllegalArgumentException("Refresh token cannot be blank"))
        }
        return repository.refresh(refreshToken)
    }
}
