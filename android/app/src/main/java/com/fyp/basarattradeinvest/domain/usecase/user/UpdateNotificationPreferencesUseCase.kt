package com.fyp.basarattradeinvest.domain.usecase.user

import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateNotificationPrefsRequestDto
import com.fyp.basarattradeinvest.domain.repository.UsersRepository

class UpdateNotificationPreferencesUseCase(private val repository: UsersRepository) {
    suspend operator fun invoke(request: UpdateNotificationPrefsRequestDto): Result<Unit> {
        return repository.updateNotificationPreferences(request)
    }
}
