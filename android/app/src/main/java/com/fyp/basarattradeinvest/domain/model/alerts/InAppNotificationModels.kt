package com.fyp.basarattradeinvest.domain.model.alerts

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Domain entity for an in-app notification.
 */
data class InAppNotification(
    val id: String,
    val userId: String,
    val ruleId: String?,
    val title: String,
    val message: String?,
    val isRead: Boolean,
    val createdAt: String
) {
    val formattedTime: String
        get() = formatRelativeNotificationTime(createdAt)
}

/**
 * Domain entity for the notification feed and pagination state.
 */
data class NotificationFeed(
    val items: List<InAppNotification>,
    val total: Int,
    val page: Int,
    val limit: Int,
    val hasMore: Boolean
) {
    val unreadCount: Int
        get() = items.count { !it.isRead }
}

private fun formatRelativeNotificationTime(isoString: String): String {
    return try {
        val inputFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val cleanIso = if (isoString.contains(".")) {
            isoString.substringBefore(".")
        } else {
            isoString.removeSuffix("Z")
        }
        val date = inputFormat.parse(cleanIso) ?: return isoString
        val diffMs = Date().time - date.time
        val minutes = diffMs / (1000 * 60)
        val hours = minutes / 60
        val days = hours / 24

        when {
            minutes < 1 -> "Just now"
            minutes < 60 -> "${minutes}m ago"
            hours < 24 -> "${hours}h ago"
            days < 7 -> "${days}d ago"
            else -> {
                val outputFormat = SimpleDateFormat("MMM dd, yyyy", Locale.US)
                outputFormat.format(date)
            }
        }
    } catch (_: Exception) {
        isoString.take(10)
    }
}
