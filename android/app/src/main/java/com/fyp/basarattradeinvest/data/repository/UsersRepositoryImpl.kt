package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.UsersApiService
import com.fyp.basarattradeinvest.data.remote.dto.user.InvestmentProfileOptionsDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateNotificationPrefsRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateProfileRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UserProfileResponseDto
import com.fyp.basarattradeinvest.domain.model.auth.InvestmentProfileOptions
import com.fyp.basarattradeinvest.domain.model.auth.UserProfile
import com.fyp.basarattradeinvest.domain.repository.UsersRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class UsersRepositoryImpl(
    private val apiService: UsersApiService = NetworkClient.usersApiService
) : UsersRepository {

    private var cachedOptions: InvestmentProfileOptions? = null

    override suspend fun getCurrentUser(): Result<UserProfile> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getCurrentUser()
            if (response.isSuccessful) {
                val dto = response.body() ?: return@withContext Result.failure(
                    Exception("Empty response received from user profile endpoint")
                )
                val domain = mapProfileDtoToDomain(dto)

                // Update session state with fresh details
                SessionManager.saveSession(
                    accessToken = SessionManager.getAccessToken().orEmpty(),
                    refreshToken = SessionManager.getRefreshToken().orEmpty(),
                    userId = domain.id,
                    email = domain.email,
                    fullName = domain.fullName
                )

                Result.success(domain)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun updateUserProfile(request: UpdateProfileRequestDto): Result<UserProfile> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.updateUserProfile(request)
            if (response.isSuccessful) {
                val dto = response.body() ?: return@withContext Result.failure(
                    Exception("Empty response received from update profile endpoint")
                )
                val domain = mapProfileDtoToDomain(dto)

                // Keep local session details in sync
                SessionManager.saveSession(
                    accessToken = SessionManager.getAccessToken().orEmpty(),
                    refreshToken = SessionManager.getRefreshToken().orEmpty(),
                    userId = domain.id,
                    email = domain.email,
                    fullName = domain.fullName
                )

                Result.success(domain)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun setUserProfile(request: UpdateProfileRequestDto): Result<UserProfile> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.setUserProfile(request)
            if (response.isSuccessful) {
                val dto = response.body() ?: return@withContext Result.failure(
                    Exception("Empty response received from set profile endpoint")
                )
                val domain = mapProfileDtoToDomain(dto)

                SessionManager.saveSession(
                    accessToken = SessionManager.getAccessToken().orEmpty(),
                    refreshToken = SessionManager.getRefreshToken().orEmpty(),
                    userId = domain.id,
                    email = domain.email,
                    fullName = domain.fullName
                )

                Result.success(domain)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun updateNotificationPreferences(
        request: UpdateNotificationPrefsRequestDto
    ): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.updateNotificationPreferences(request)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getInvestmentProfileOptions(
        forceRefresh: Boolean
    ): Result<InvestmentProfileOptions> = withContext(Dispatchers.IO) {
        if (!forceRefresh && cachedOptions != null) {
            return@withContext Result.success(cachedOptions!!)
        }

        try {
            val response = apiService.getInvestmentProfileOptions()
            if (response.isSuccessful) {
                val dto = response.body() ?: return@withContext Result.failure(
                    Exception("Empty response received from options endpoint")
                )
                val domain = mapOptionsDtoToDomain(dto)
                cachedOptions = domain
                Result.success(domain)
            } else {
                if (cachedOptions != null) {
                    Result.success(cachedOptions!!)
                } else {
                    val error = NetworkErrorParser.parseError(response)
                    Result.failure(Exception(error))
                }
            }
        } catch (e: Exception) {
            if (cachedOptions != null) {
                Result.success(cachedOptions!!)
            } else {
                Result.failure(e)
            }
        }
    }

    private fun mapProfileDtoToDomain(dto: UserProfileResponseDto): UserProfile {
        return UserProfile(
            id = dto.id,
            email = dto.email,
            username = dto.username,
            fullName = dto.fullName,
            avatarUrl = dto.avatarUrl,
            isActive = dto.isActive,
            isVerified = dto.isVerified,
            riskTolerance = dto.riskTolerance,
            sectorPreferences = dto.sectorPreferences ?: emptyList(),
            investmentHorizon = dto.investmentHorizon,
            createdAt = dto.createdAt
        )
    }

    private fun mapOptionsDtoToDomain(dto: InvestmentProfileOptionsDto): InvestmentProfileOptions {
        return InvestmentProfileOptions(
            riskTolerances = dto.riskTolerances,
            investmentHorizons = dto.investmentHorizons,
            sectors = dto.sectors,
            noPreference = dto.noPreference ?: "All Sectors",
            description = dto.description
        )
    }
}
