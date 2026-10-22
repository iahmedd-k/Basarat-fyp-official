package com.fyp.basarattradeinvest.domain.repository

interface DevicesRepository {
    suspend fun registerDevice(fcmToken: String, deviceName: String): Result<String>
    suspend fun unregisterDevice(deviceId: String): Result<Unit>
}
