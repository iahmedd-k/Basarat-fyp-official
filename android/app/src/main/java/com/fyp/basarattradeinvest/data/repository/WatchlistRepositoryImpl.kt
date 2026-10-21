package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.WatchlistApiService
import com.fyp.basarattradeinvest.data.remote.dto.watchlist.WatchlistDetailResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.watchlist.WatchlistItemCreateRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.watchlist.WatchlistItemResponseDto
import com.fyp.basarattradeinvest.domain.model.watchlist.Watchlist
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistItem
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistMembership
import com.fyp.basarattradeinvest.domain.repository.WatchlistRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.withContext

class WatchlistRepositoryImpl(
    private val api: WatchlistApiService = NetworkClient.watchlistApiService
) : WatchlistRepository {

    private val _watchlistUpdates = MutableSharedFlow<Watchlist>(extraBufferCapacity = 1)
    override val watchlistUpdates = _watchlistUpdates.asSharedFlow()
    @Volatile private var cachedDefault: Watchlist? = null

    override suspend fun getDefaultWatchlist(): Result<Watchlist> = withContext(Dispatchers.IO) {
        if (!SessionManager.hasValidSession()) return@withContext unauthenticatedResult()
        try {
            val response = api.getDefaultWatchlist()
            if (response.isSuccessful) {
                val dto = response.body()
                    ?: return@withContext Result.failure(Exception("The watchlist response was empty."))
                map(dto).also { cachedDefault = it }.let { Result.success(it) }
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (cancelled: kotlinx.coroutines.CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(error)
        }
    }

    override suspend fun checkSymbol(symbol: String): Result<WatchlistMembership> = withContext(Dispatchers.IO) {
        if (!SessionManager.hasValidSession()) return@withContext unauthenticatedResult()
        try {
            val response = api.checkSymbol(symbol.trim().uppercase())
            if (response.isSuccessful) {
                val body = response.body()
                    ?: return@withContext Result.failure(Exception("The watchlist check response was empty."))
                Result.success(WatchlistMembership(body.symbol, body.isInWatchlist, body.watchlistIds))
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (cancelled: kotlinx.coroutines.CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(error)
        }
    }

    override suspend fun addToDefaultWatchlist(symbol: String): Result<Watchlist> = withContext(Dispatchers.IO) {
        if (!SessionManager.hasValidSession()) return@withContext unauthenticatedResult()
        try {
            // Resolve the default ID for the currently authenticated account before adding.
            val defaultResponse = api.getDefaultWatchlist()
            if (!defaultResponse.isSuccessful || defaultResponse.body() == null) {
                return@withContext Result.failure(Exception(NetworkErrorParser.parseError(defaultResponse)))
            }
            val watchlist = map(defaultResponse.body()!!).also { cachedDefault = it }
            if (watchlist.items.any { it.symbol.equals(symbol, ignoreCase = true) }) {
                return@withContext Result.success(watchlist)
            }
            val response = api.addItem(watchlist.id, WatchlistItemCreateRequestDto(symbol.trim().uppercase()))
            if (!response.isSuccessful || response.body() == null) {
                return@withContext Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
            val updated = watchlist.copy(
                items = (watchlist.items + map(response.body()!!)).distinctBy { it.symbol.uppercase() }
            )
            cachedDefault = updated
            _watchlistUpdates.emit(updated)
            Result.success(updated)
        } catch (cancelled: kotlinx.coroutines.CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(error)
        }
    }

    override suspend fun removeFromWatchlists(
        symbol: String,
        watchlistIds: List<String>
    ): Result<Unit> = withContext(Dispatchers.IO) {
        if (!SessionManager.hasValidSession()) return@withContext unauthenticatedResult()
        if (watchlistIds.isEmpty()) return@withContext Result.failure(Exception("This stock is not in a watchlist."))
        try {
            for (watchlistId in watchlistIds.distinct()) {
                val response = api.removeItem(watchlistId, symbol.trim().uppercase())
                if (!response.isSuccessful) {
                    return@withContext Result.failure(Exception(NetworkErrorParser.parseError(response)))
                }
                cachedDefault?.takeIf { it.id == watchlistId }?.let { current ->
                    val updated = current.copy(items = current.items.filterNot { it.symbol.equals(symbol, true) })
                    cachedDefault = updated
                    _watchlistUpdates.emit(updated)
                }
            }
            Result.success(Unit)
        } catch (cancelled: kotlinx.coroutines.CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(error)
        }
    }

    private fun map(dto: WatchlistDetailResponseDto) = Watchlist(
        id = dto.id,
        name = dto.name,
        items = dto.items.map(::map).distinctBy { it.symbol.uppercase() }
    )

    private fun map(dto: WatchlistItemResponseDto) = WatchlistItem(
        id = dto.id,
        watchlistId = dto.watchlistId,
        symbol = dto.symbol,
        name = dto.name,
        targetPrice = dto.targetPrice,
        notes = dto.notes,
        currentPrice = dto.currentPrice,
        change = dto.change,
        changePercent = dto.changePct,
        isStale = dto.isStale
    )

    private fun <T> unauthenticatedResult(): Result<T> =
        Result.failure(IllegalStateException("Sign in to view and manage your watchlist."))
}
