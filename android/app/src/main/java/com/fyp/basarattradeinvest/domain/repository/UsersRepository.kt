package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateNotificationPrefsRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateProfileRequestDto
import com.fyp.basarattradeinvest.domain.model.auth.InvestmentProfileOptions
import com.fyp.basarattradeinvest.domain.model.auth.UserProfile

interface UsersRepository {

    suspend fun getCurrentUser(): Result<UserProfile>

    suspend fun updateUserProfile(request: UpdateProfileRequestDto): Result<UserProfile>

    suspend fun setUserProfile(request: UpdateProfileRequestDto): Result<UserProfile>

    suspend fun updateNotificationPreferences(request: UpdateNotificationPrefsRequestDto): Result<Unit>

    suspend fun getInvestmentProfileOptions(forceRefresh: Boolean = false): Result<InvestmentProfileOptions>
}
