package com.fyp.basarattradeinvest.core.notifications

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ProcessLifecycleOwner
import com.fyp.basarattradeinvest.MainActivity
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

class BasaratFirebaseService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        SessionManager.init(applicationContext)
        DeviceRegistrationScheduler.enqueue(applicationContext, token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val target = NotificationTarget.from(message)
        val appIsForeground = ProcessLifecycleOwner.get().lifecycle.currentState
            .isAtLeast(Lifecycle.State.STARTED)

        if (appIsForeground) {
            NotificationEvents.publish(target)
            return
        }

        // Notification payloads are displayed by FCM while backgrounded. Only create a
        // local system notification for data-only messages to avoid duplicate alerts.
        if (message.notification == null) showSystemNotification(target)
    }

    private fun showSystemNotification(target: NotificationTarget) {
        NotificationChannels.create(applicationContext)
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            target.putIn(this)
        }
        val stableId = target.notificationId?.hashCode()
            ?: target.symbol?.hashCode()
            ?: System.currentTimeMillis().toInt()
        val pendingIntent = PendingIntent.getActivity(
            this,
            stableId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(this, NotificationChannels.forType(target.type))
            .setSmallIcon(R.drawable.ic_alert_bell)
            .setContentTitle(target.title)
            .setContentText(target.body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(target.body))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        try {
            NotificationManagerCompat.from(this).notify(stableId, notification)
        } catch (_: SecurityException) {
            // Notifications may be disabled by the user or permission may be denied.
        }
    }
}
