package com.fyp.basarattradeinvest.profile

import com.fyp.basarattradeinvest.data.remote.api.UsersApiService
import com.fyp.basarattradeinvest.data.remote.dto.user.InvestmentProfileOptionsDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateNotificationPrefsRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateProfileRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UserPayloads
import com.fyp.basarattradeinvest.data.remote.dto.user.UserProfileResponseDto
import com.fyp.basarattradeinvest.data.repository.UsersRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.user.GetCurrentUserProfileUseCase
import com.fyp.basarattradeinvest.domain.usecase.user.GetInvestmentProfileOptionsUseCase
import com.fyp.basarattradeinvest.domain.usecase.user.UpdateNotificationPreferencesUseCase
import com.fyp.basarattradeinvest.domain.usecase.user.UpdateUserProfileUseCase
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class UsersModuleUnitTest {

    private val fakeApiService = object : UsersApiService {
        var shouldFail = false

        override suspend fun getCurrentUser(): Response<UserProfileResponseDto> {
            return if (shouldFail) {
                val errorBody = "{\"detail\":\"Unauthorized\"}".toResponseBody("application/json".toMediaType())
                Response.error(401, errorBody)
            } else {
                Response.success(
                    UserProfileResponseDto(
                        id = "user_abc_123",
                        email = "trader@basarat.pk",
                        username = "basarat_trader",
                        fullName = "Basarat Trader",
                        avatarUrl = "https://example.com/avatar.jpg",
                        isActive = true,
                        isVerified = true,
                        riskTolerance = "moderate",
                        sectorPreferences = listOf("Commercial Banks", "Technology"),
                        investmentHorizon = "medium_term",
                        createdAt = "2026-09-22T00:00:00Z"
                    )
                )
            }
        }

        override suspend fun setUserProfile(request: UpdateProfileRequestDto): Response<UserProfileResponseDto> {
            return Response.success(
                UserProfileResponseDto(
                    id = "user_abc_123",
                    email = "trader@basarat.pk",
                    username = "basarat_trader",
                    fullName = request.fullName ?: "Basarat Trader",
                    avatarUrl = request.avatarUrl,
                    isActive = true,
                    isVerified = true,
                    riskTolerance = request.riskTolerance ?: "moderate",
                    sectorPreferences = request.sectorPreferences ?: emptyList(),
                    investmentHorizon = request.investmentHorizon ?: "medium_term",
                    createdAt = "2026-09-22T00:00:00Z"
                )
            )
        }

        override suspend fun updateUserProfile(request: UpdateProfileRequestDto): Response<UserProfileResponseDto> {
            return if (shouldFail) {
                val errorBody = "{\"detail\":\"Validation error\"}".toResponseBody("application/json".toMediaType())
                Response.error(422, errorBody)
            } else {
                Response.success(
                    UserProfileResponseDto(
                        id = "user_abc_123",
                        email = "trader@basarat.pk",
                        username = "basarat_trader",
                        fullName = request.fullName ?: "Updated Trader",
                        avatarUrl = request.avatarUrl,
                        isActive = true,
                        isVerified = true,
                        riskTolerance = request.riskTolerance ?: "aggressive",
                        sectorPreferences = request.sectorPreferences ?: listOf("Cement"),
                        investmentHorizon = request.investmentHorizon ?: "long_term",
                        createdAt = "2026-09-22T00:00:00Z"
                    )
                )
            }
        }

        override suspend fun updateNotificationPreferences(request: UpdateNotificationPrefsRequestDto): Response<Map<String, Any>> {
            return if (shouldFail) {
                val errorBody = "{\"detail\":\"Failed to update notifications\"}".toResponseBody("application/json".toMediaType())
                Response.error(400, errorBody)
            } else {
                Response.success(mapOf("success" to true))
            }
        }

        override suspend fun getInvestmentProfileOptions(): Response<InvestmentProfileOptionsDto> {
            return Response.success(
                InvestmentProfileOptionsDto(
                    riskTolerances = listOf("conservative", "moderate", "aggressive"),
                    investmentHorizons = listOf("short_term", "medium_term", "long_term"),
                    sectors = listOf("All Sectors", "Commercial Banks", "Oil & Gas", "Technology"),
                    noPreference = "All Sectors",
                    description = "Select allowed risk tolerances"
                )
            )
        }
    }

    private val usersRepository = UsersRepositoryImpl(fakeApiService)

    @Test
    fun testGetCurrentUserProfileSuccess() = runBlocking {
        fakeApiService.shouldFail = false
        val result = usersRepository.getCurrentUser()

        assertTrue(result.isSuccess)
        val profile = result.getOrNull()
        assertNotNull(profile)
        assertEquals("user_abc_123", profile?.id)
        assertEquals("trader@basarat.pk", profile?.email)
        assertEquals("moderate", profile?.riskTolerance)
        assertEquals("medium_term", profile?.investmentHorizon)
        assertEquals(2, profile?.sectorPreferences?.size)
    }

    @Test
    fun testGetCurrentUserProfileFailure() = runBlocking {
        fakeApiService.shouldFail = true
        val result = usersRepository.getCurrentUser()

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("Unauthorized") == true)
    }

    @Test
    fun testUpdateUserProfileSuccess() = runBlocking {
        fakeApiService.shouldFail = false
        val request = UpdateProfileRequestDto(
            fullName = "New Name",
            riskTolerance = "aggressive",
            investmentHorizon = "long_term",
            sectorPreferences = listOf("Technology")
        )
        val result = usersRepository.updateUserProfile(request)

        assertTrue(result.isSuccess)
        val updated = result.getOrNull()
        assertEquals("New Name", updated?.fullName)
        assertEquals("aggressive", updated?.riskTolerance)
        assertEquals("long_term", updated?.investmentHorizon)
    }

    @Test
    fun testGetInvestmentProfileOptions() = runBlocking {
        val result = usersRepository.getInvestmentProfileOptions(forceRefresh = true)

        assertTrue(result.isSuccess)
        val options = result.getOrNull()
        assertNotNull(options)
        assertEquals(3, options?.riskTolerances?.size)
        assertEquals(3, options?.investmentHorizons?.size)
        assertEquals(4, options?.sectors?.size)
        assertEquals("All Sectors", options?.noPreference)
    }

    @Test
    fun testUpdateNotificationPreferences() = runBlocking {
        fakeApiService.shouldFail = false
        val request = UpdateNotificationPrefsRequestDto(
            channels = listOf("push", "email"),
            categories = listOf("POST_LIKED", "COMMENT_REPLIED")
        )
        val result = usersRepository.updateNotificationPreferences(request)

        assertTrue(result.isSuccess)
    }

    @Test
    fun testUseCases() = runBlocking {
        val getProfileUseCase = GetCurrentUserProfileUseCase(usersRepository)
        val updateProfileUseCase = UpdateUserProfileUseCase(usersRepository)
        val getOptionsUseCase = GetInvestmentProfileOptionsUseCase(usersRepository)
        val updateNotifUseCase = UpdateNotificationPreferencesUseCase(usersRepository)

        fakeApiService.shouldFail = false
        assertTrue(getProfileUseCase().isSuccess)
        assertTrue(getOptionsUseCase().isSuccess)
        assertTrue(updateProfileUseCase(UpdateProfileRequestDto(fullName = "Test")).isSuccess)
        assertTrue(updateNotifUseCase(UpdateNotificationPrefsRequestDto(channels = listOf("push"))).isSuccess)
    }

    @Test
    fun testPreBuiltUserPayloads() {
        assertNotNull(UserPayloads.DEFAULT_PROFILE_UPDATE)
        assertEquals("moderate", UserPayloads.DEFAULT_PROFILE_UPDATE.riskTolerance)
        assertEquals("medium_term", UserPayloads.DEFAULT_PROFILE_UPDATE.investmentHorizon)

        assertNotNull(UserPayloads.CONSERVATIVE_RISK_PROFILE)
        assertEquals("conservative", UserPayloads.CONSERVATIVE_RISK_PROFILE.riskTolerance)
        assertEquals("long_term", UserPayloads.CONSERVATIVE_RISK_PROFILE.investmentHorizon)

        assertNotNull(UserPayloads.DEFAULT_NOTIFICATION_PREFS)
        assertTrue(UserPayloads.DEFAULT_NOTIFICATION_PREFS.channels?.contains("push") == true)
    }
}
