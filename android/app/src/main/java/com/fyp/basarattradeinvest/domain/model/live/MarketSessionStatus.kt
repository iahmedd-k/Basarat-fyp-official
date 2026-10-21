package com.fyp.basarattradeinvest.domain.model.live

/**
 * Trading-session state reported by GET /api/v1/market/live.
 *
 * A missing value means the session is unknown; callers must hide the indicator
 * rather than default to closed, which is what made the dashboard claim
 * "Market Closed" during trading hours.
 */
data class MarketSessionStatus(val isOpen: Boolean) {
    val label: String get() = if (isOpen) "Market Open" else "Market Closed"
}
