package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.user.InvestmentProfileOptionsDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateNotificationPrefsRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateProfileRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.user.UserProfileResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST

/**
 * Retrofit service definition for BASARAT User Profile, Investment Preferences,
 * and Notification Preferences endpoints.
 * Defined strictly according to OpenAPI / Swagger contract at:
 * https://basarat-fyp-official.onrender.com/docs
 */
interface UsersApiService {

    @GET("api/v1/users/me")
    suspend fun getCurrentUser(): Response<UserProfileResponseDto>

    @POST("api/v1/users/me")
    suspend fun setUserProfile(
        @Body request: UpdateProfileRequestDto
    ): Response<UserProfileResponseDto>

    @PATCH("api/v1/users/me")
    suspend fun updateUserProfile(
        @Body request: UpdateProfileRequestDto
    ): Response<UserProfileResponseDto>

    @PATCH("api/v1/users/me/notification-preferences")
    suspend fun updateNotificationPreferences(
        @Body request: UpdateNotificationPrefsRequestDto
    ): Response<Map<String, Any>>

    @GET("api/v1/users/investment-profile/options")
    suspend fun getInvestmentProfileOptions(): Response<InvestmentProfileOptionsDto>
}
