package com.fyp.basarattradeinvest.core.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build

object NotificationChannels {
    const val MARKET = "basarat_market_alerts"
    const val PORTFOLIO = "basarat_portfolio_risk"
    const val COMMUNITY = "basarat_community"
    const val GENERAL = "basarat_general"

    fun create(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannels(
            listOf(
                NotificationChannel(MARKET, "Market alerts", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Price and watchlist alerts"
                },
                NotificationChannel(PORTFOLIO, "Portfolio and risk", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Portfolio and risk updates"
                },
                NotificationChannel(COMMUNITY, "Community", NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = "Community likes, comments and replies"
                },
                NotificationChannel(GENERAL, "General", NotificationManager.IMPORTANCE_DEFAULT).apply {
                    description = "Other BASARAT notifications"
                }
            )
        )
    }

    fun forType(type: String?): String = when (type?.uppercase()) {
        "PRICE_ALERT", "WATCHLIST_ALERT", "MARKET_ALERT" -> MARKET
        "PORTFOLIO_RISK", "RISK_ALERT" -> PORTFOLIO
        "POST_LIKED", "POST_COMMENTED", "COMMENT_REPLIED", "USER_FOLLOWED",
        "POST_AUTO_HIDDEN", "POST_RESTORED", "POST_MODERATION_DELETED" -> COMMUNITY
        else -> GENERAL
    }
}
