package com.fyp.basarattradeinvest.domain.usecase.auth

import com.fyp.basarattradeinvest.domain.model.auth.User
import com.fyp.basarattradeinvest.domain.repository.AuthRepository

class CheckSessionUseCase(private val repository: AuthRepository) {
    operator fun invoke(): Boolean {
        return repository.isUserAuthenticated()
    }

    fun getUser(): User? {
        return repository.getCurrentUser()
    }
}
