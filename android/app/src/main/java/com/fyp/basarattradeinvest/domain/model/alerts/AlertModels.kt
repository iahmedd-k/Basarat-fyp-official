package com.fyp.basarattradeinvest.domain.model.alerts

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Domain entity for a triggered alert / notification event.
 */
data class AlertItem(
    val id: String,
    val userId: String,
    val ruleId: String?,
    val title: String,
    val message: String?,
    val isRead: Boolean,
    val createdAt: String
) {
    val formattedTime: String
        get() = formatRelativeTime(createdAt)
}

/** Result fields needed by Stock Detail after the backend creates a quick rule. */
data class QuickAlertResult(
    val symbol: String,
    val stockId: String,
    val basePrice: Double,
    val percentThreshold: Double,
    val direction: String,
    val message: String
)

private fun formatIsoDate(isoString: String): String {
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
        val outputFormat = SimpleDateFormat("MMM dd, yyyy", Locale.US)
        outputFormat.format(date)
    } catch (_: Exception) {
        isoString.take(10)
    }
}

private fun formatRelativeTime(isoString: String): String {
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
                val outputFormat = SimpleDateFormat("MMM dd", Locale.US)
                outputFormat.format(date)
            }
        }
    } catch (_: Exception) {
        isoString.take(10)
    }
}
