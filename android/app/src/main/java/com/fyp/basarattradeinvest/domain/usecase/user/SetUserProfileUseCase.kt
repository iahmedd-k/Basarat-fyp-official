package com.fyp.basarattradeinvest.domain.usecase.user

import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateProfileRequestDto
import com.fyp.basarattradeinvest.domain.model.auth.UserProfile
import com.fyp.basarattradeinvest.domain.repository.UsersRepository

class SetUserProfileUseCase(private val repository: UsersRepository) {
    suspend operator fun invoke(request: UpdateProfileRequestDto): Result<UserProfile> {
        return repository.setUserProfile(request)
    }
}
