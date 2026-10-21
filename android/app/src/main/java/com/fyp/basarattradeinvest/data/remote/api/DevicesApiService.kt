package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.notifications.DeviceRegisterRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.notifications.DeviceRegisterResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.POST
import retrofit2.http.Path

interface DevicesApiService {
    @POST("api/v1/devices/register")
    suspend fun registerDevice(
        @Body request: DeviceRegisterRequestDto
    ): Response<DeviceRegisterResponseDto>

    @DELETE("api/v1/devices/{device_id}")
    suspend fun unregisterDevice(
        @Path("device_id") deviceId: String
    ): Response<Unit>
}
