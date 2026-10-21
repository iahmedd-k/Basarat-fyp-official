package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.DevicesApiService
import com.fyp.basarattradeinvest.data.remote.dto.notifications.DeviceRegisterRequestDto
import com.fyp.basarattradeinvest.domain.repository.DevicesRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class DevicesRepositoryImpl(
    private val apiService: DevicesApiService = NetworkClient.devicesApiService
) : DevicesRepository {
    override suspend fun registerDevice(
        fcmToken: String,
        deviceName: String
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.registerDevice(
                DeviceRegisterRequestDto(
                    fcmToken = fcmToken,
                    deviceName = deviceName
                )
            )
            val deviceId = response.body()?.id
            if (response.isSuccessful && !deviceId.isNullOrBlank()) {
                Result.success(deviceId)
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (error: Exception) {
            Result.failure(error)
        }
    }

    override suspend fun unregisterDevice(deviceId: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.unregisterDevice(deviceId)
            if (response.isSuccessful) Result.success(Unit)
            else Result.failure(Exception(NetworkErrorParser.parseError(response)))
        } catch (error: Exception) {
            Result.failure(error)
        }
    }
}
