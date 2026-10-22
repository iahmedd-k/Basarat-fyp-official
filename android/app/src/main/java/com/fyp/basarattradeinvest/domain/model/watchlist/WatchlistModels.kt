package com.fyp.basarattradeinvest.domain.model.watchlist

data class Watchlist(
    val id: String,
    val name: String,
    val items: List<WatchlistItem>
)

data class WatchlistItem(
    val id: String,
    val watchlistId: String,
    val symbol: String,
    val name: String?,
    val targetPrice: Double? = null,
    val notes: String? = null,
    val currentPrice: Double?,
    val change: Double?,
    val changePercent: Double?,
    val isStale: Boolean
)

data class WatchlistMembership(
    val symbol: String,
    val isInWatchlist: Boolean,
    val watchlistIds: List<String>
)
