package com.fyp.basarattradeinvest.core.notifications

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.google.firebase.messaging.FirebaseMessaging
import java.util.concurrent.TimeUnit

object DeviceRegistrationScheduler {
    const val UNIQUE_WORK_NAME = "basarat_fcm_device_registration"

    fun requestCurrentToken(context: Context) {
        val appContext = context.applicationContext
        SessionManager.init(appContext)
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (task.isSuccessful) {
                task.result?.takeIf(String::isNotBlank)?.let { enqueue(appContext, it) }
            } else {
                SessionManager.getPendingFcmToken()?.let { enqueue(appContext, it) }
            }
        }
    }

    fun enqueue(context: Context, token: String) {
        if (token.isBlank()) return
        val appContext = context.applicationContext
        SessionManager.init(appContext)
        SessionManager.storePendingFcmToken(token)
        if (!SessionManager.hasValidSession()) return
        if (SessionManager.getDeviceId() != null && SessionManager.getRegisteredFcmToken() == token) return

        val request = OneTimeWorkRequestBuilder<DeviceRegistrationWorker>()
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()

        WorkManager.getInstance(appContext).enqueueUniqueWork(
            UNIQUE_WORK_NAME,
            ExistingWorkPolicy.REPLACE,
            request
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context.applicationContext).cancelUniqueWork(UNIQUE_WORK_NAME)
    }
}
