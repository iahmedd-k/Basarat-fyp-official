package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.watchlist.Watchlist
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistMembership
import kotlinx.coroutines.flow.SharedFlow

interface WatchlistRepository {
    val watchlistUpdates: SharedFlow<Watchlist>
    suspend fun getDefaultWatchlist(): Result<Watchlist>
    suspend fun checkSymbol(symbol: String): Result<WatchlistMembership>
    suspend fun addToDefaultWatchlist(symbol: String): Result<Watchlist>
    suspend fun removeFromWatchlists(symbol: String, watchlistIds: List<String>): Result<Unit>
}
