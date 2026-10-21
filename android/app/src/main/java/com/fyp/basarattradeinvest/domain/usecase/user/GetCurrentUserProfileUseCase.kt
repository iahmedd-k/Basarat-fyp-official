package com.fyp.basarattradeinvest.domain.usecase.user

import com.fyp.basarattradeinvest.domain.model.auth.UserProfile
import com.fyp.basarattradeinvest.domain.repository.UsersRepository

class GetCurrentUserProfileUseCase(private val repository: UsersRepository) {
    suspend operator fun invoke(): Result<UserProfile> {
        return repository.getCurrentUser()
    }
}
