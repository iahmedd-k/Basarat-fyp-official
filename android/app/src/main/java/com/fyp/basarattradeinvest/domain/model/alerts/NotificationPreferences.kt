package com.fyp.basarattradeinvest.domain.model.alerts

data class NotificationPreferences(
    val channels: List<String>,
    val categories: List<String>
)
