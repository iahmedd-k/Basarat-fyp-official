package com.fyp.basarattradeinvest.core.notifications

import android.os.Build
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import android.content.Context
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.data.repository.DevicesRepositoryImpl

class DeviceRegistrationWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        SessionManager.init(applicationContext)
        val token = SessionManager.getPendingFcmToken() ?: return Result.success()

        if (!SessionManager.hasValidSession()) return Result.success()
        if (SessionManager.getDeviceId() != null && SessionManager.getRegisteredFcmToken() == token) {
            return Result.success()
        }

        val registration = DevicesRepositoryImpl().registerDevice(token, deviceName())
        return registration.fold(
            onSuccess = { deviceId ->
                SessionManager.saveDeviceRegistration(deviceId, token)
                Result.success()
            },
            onFailure = {
                if (runAttemptCount >= MAX_ATTEMPTS) Result.failure() else Result.retry()
            }
        )
    }

    private fun deviceName(): String {
        val manufacturer = Build.MANUFACTURER.orEmpty().trim()
        val model = Build.MODEL.orEmpty().trim()
        val friendlyManufacturer = manufacturer.replaceFirstChar { it.uppercase() }
        return when {
            model.isBlank() -> friendlyManufacturer.ifBlank { "Android device" }
            manufacturer.isBlank() || model.startsWith(manufacturer, ignoreCase = true) -> model
            else -> "$friendlyManufacturer $model"
        }.take(MAX_DEVICE_NAME_LENGTH)
    }

    companion object {
        private const val MAX_ATTEMPTS = 8
        private const val MAX_DEVICE_NAME_LENGTH = 255
    }
}
