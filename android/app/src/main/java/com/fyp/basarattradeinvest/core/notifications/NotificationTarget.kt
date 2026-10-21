package com.fyp.basarattradeinvest.core.notifications

import android.content.Intent
import com.google.firebase.messaging.RemoteMessage

data class NotificationTarget(
    val notificationId: String? = null,
    val type: String? = null,
    val screen: String? = null,
    val symbol: String? = null,
    val relatedId: String? = null,
    val title: String = "BASARAT",
    val body: String = "You have a new notification"
) {
    fun putIn(intent: Intent) {
        notificationId?.let { intent.putExtra(EXTRA_NOTIFICATION_ID, it) }
        type?.let { intent.putExtra(EXTRA_TYPE, it) }
        screen?.let { intent.putExtra(EXTRA_SCREEN, it) }
        symbol?.let { intent.putExtra(EXTRA_SYMBOL, it) }
        relatedId?.let { intent.putExtra(EXTRA_RELATED_ID, it) }
        intent.putExtra(EXTRA_TITLE, title)
        intent.putExtra(EXTRA_BODY, body)
    }

    companion object {
        const val EXTRA_NOTIFICATION_ID = "basarat_notification_id"
        const val EXTRA_TYPE = "basarat_notification_type"
        const val EXTRA_SCREEN = "basarat_notification_screen"
        const val EXTRA_SYMBOL = "basarat_notification_symbol"
        const val EXTRA_RELATED_ID = "basarat_notification_related_id"
        const val EXTRA_TITLE = "basarat_notification_title"
        const val EXTRA_BODY = "basarat_notification_body"

        fun from(message: RemoteMessage): NotificationTarget {
            val data = message.data
            return NotificationTarget(
                notificationId = data["notification_id"] ?: data["id"],
                type = data["type"],
                screen = data["screen"],
                symbol = data["symbol"],
                relatedId = data["related_id"] ?: data["relatedId"],
                title = message.notification?.title ?: data["title"] ?: "BASARAT",
                body = message.notification?.body ?: data["body"] ?: data["message"] ?: "You have a new notification"
            )
        }

        fun from(intent: Intent?): NotificationTarget? {
            val extras = intent?.extras ?: return null
            val hasPayload = extras.containsKey(EXTRA_SCREEN) || extras.containsKey(EXTRA_NOTIFICATION_ID) ||
                extras.containsKey("screen") || extras.containsKey("notification_id")
            if (!hasPayload) return null
            return NotificationTarget(
                notificationId = extras.getString(EXTRA_NOTIFICATION_ID) ?: extras.getString("notification_id") ?: extras.getString("id"),
                type = extras.getString(EXTRA_TYPE) ?: extras.getString("type"),
                screen = extras.getString(EXTRA_SCREEN) ?: extras.getString("screen"),
                symbol = extras.getString(EXTRA_SYMBOL) ?: extras.getString("symbol"),
                relatedId = extras.getString(EXTRA_RELATED_ID) ?: extras.getString("related_id") ?: extras.getString("relatedId"),
                title = extras.getString(EXTRA_TITLE) ?: extras.getString("title") ?: "BASARAT",
                body = extras.getString(EXTRA_BODY) ?: extras.getString("body") ?: "You have a new notification"
            )
        }
    }
}
