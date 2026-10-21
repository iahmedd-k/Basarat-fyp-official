package com.fyp.basarattradeinvest.feature.watchlist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistItem
import com.fyp.basarattradeinvest.domain.repository.LiveMarketRepository
import com.fyp.basarattradeinvest.domain.repository.WatchlistRepository
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface WatchlistScreenUiState {
    data object Loading : WatchlistScreenUiState

    data class Loaded(
        val items: List<WatchlistItem> = emptyList(),
        val pendingRemovals: Set<String> = emptySet()
    ) : WatchlistScreenUiState

    data class Error(val message: String) : WatchlistScreenUiState
}

class WatchlistViewModel(
    private val watchlistRepository: WatchlistRepository = NetworkClient.watchlistRepository,
    private val liveMarketRepository: LiveMarketRepository = NetworkClient.liveMarketRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<WatchlistScreenUiState>(WatchlistScreenUiState.Loading)
    val uiState: StateFlow<WatchlistScreenUiState> = _uiState.asStateFlow()

    private val _messages = MutableSharedFlow<String>(extraBufferCapacity = 1)
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    private var isLoading = false
    private var isLiveUpdatesActive = false

    init {
        load()

        viewModelScope.launch {
            watchlistRepository.watchlistUpdates.collect { watchlist ->
                val merged = watchlist.items.map { mergeQuote(it, liveMarketRepository.getCachedQuote(it.symbol)) }
                // update{} rather than a read-then-write: the repository emits this while a
                // removal is still returning, so the pending marks must be carried over from
                // whatever the state is at write time, not from a snapshot taken earlier.
                _uiState.update { current ->
                    WatchlistScreenUiState.Loaded(
                        items = merged,
                        pendingRemovals = (current as? WatchlistScreenUiState.Loaded)?.pendingRemovals.orEmpty()
                    )
                }
                refreshSubscriptions(merged)
            }
        }

        viewModelScope.launch {
            liveMarketRepository.quoteCache.collect { cache ->
                _uiState.update { current ->
                    val loaded = current as? WatchlistScreenUiState.Loaded ?: return@update current
                    if (loaded.items.isEmpty()) return@update current
                    loaded.copy(items = loaded.items.map { mergeQuote(it, cache[it.symbol]) })
                }
            }
        }
    }

    fun load() {
        if (isLoading) return
        isLoading = true
        viewModelScope.launch {
            try {
                watchlistRepository.getDefaultWatchlist().fold(
                    onSuccess = { watchlist ->
                        _uiState.update { current ->
                            WatchlistScreenUiState.Loaded(
                                items = watchlist.items.map {
                                    mergeQuote(it, liveMarketRepository.getCachedQuote(it.symbol))
                                },
                                pendingRemovals = (current as? WatchlistScreenUiState.Loaded)?.pendingRemovals.orEmpty()
                            )
                        }
                        refreshSubscriptions(watchlist.items)
                    },
                    // Keep an already-painted list rather than replacing it with an error banner.
                    onFailure = { error ->
                        val hadData = _uiState.value is WatchlistScreenUiState.Loaded
                        if (hadData) {
                            _messages.emit(error.message ?: "Unable to refresh your watchlist.")
                        } else {
                            _uiState.value = WatchlistScreenUiState.Error(
                                error.message ?: "Unable to load your watchlist."
                            )
                        }
                    }
                )
            } finally {
                isLoading = false
            }
        }
    }

    fun remove(symbol: String, watchlistId: String) {
        var marked = false
        _uiState.update { current ->
            val loaded = current as? WatchlistScreenUiState.Loaded ?: return@update current
            if (symbol in loaded.pendingRemovals) return@update current
            marked = true
            loaded.copy(pendingRemovals = loaded.pendingRemovals + symbol)
        }
        if (!marked) return
        viewModelScope.launch {
            watchlistRepository.removeFromWatchlists(symbol, listOf(watchlistId)).fold(
                onSuccess = {
                    // The repository publishes the updated watchlist through watchlistUpdates,
                    // so the row drops out of state; only the in-flight marker is cleared here.
                    clearPending(symbol)
                    _messages.emit("$symbol removed from watchlist")
                },
                onFailure = { error ->
                    clearPending(symbol)
                    _messages.emit(error.message ?: "Unable to remove $symbol.")
                }
            )
        }
    }

    fun setLiveUpdatesActive(active: Boolean) {
        if (isLiveUpdatesActive == active) return
        isLiveUpdatesActive = active
        val items = (_uiState.value as? WatchlistScreenUiState.Loaded)?.items.orEmpty()
        liveMarketRepository.setSubscriptions(
            owner = OWNER,
            symbols = if (active) items.map { it.symbol } else emptyList()
        )
    }

    private fun refreshSubscriptions(items: List<WatchlistItem>) {
        if (!isLiveUpdatesActive) return
        liveMarketRepository.setSubscriptions(OWNER, items.map { it.symbol })
    }

    private fun clearPending(symbol: String) {
        _uiState.update { current ->
            val loaded = current as? WatchlistScreenUiState.Loaded ?: return@update current
            loaded.copy(pendingRemovals = loaded.pendingRemovals - symbol)
        }
    }

    /**
     * A live tick overrides the REST snapshot; without one, the snapshot's own values stay.
     * Absent figures remain absent rather than being inferred.
     */
    private fun mergeQuote(item: WatchlistItem, quote: LiveQuote?): WatchlistItem {
        if (quote == null) return item
        return item.copy(
            currentPrice = quote.current ?: item.currentPrice,
            change = quote.change ?: item.change,
            changePercent = quote.changePct ?: item.changePercent,
            isStale = quote.isStale
        )
    }

    private companion object {
        const val OWNER = "watchlist"
    }
}
