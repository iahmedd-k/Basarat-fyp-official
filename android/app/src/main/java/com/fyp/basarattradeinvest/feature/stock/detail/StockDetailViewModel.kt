package com.fyp.basarattradeinvest.feature.stock.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.RecommendationsRepositoryImpl
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationDetail
import com.fyp.basarattradeinvest.domain.model.stock.StockTrade
import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.LiveQuoteSource
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository
import com.fyp.basarattradeinvest.domain.repository.StockRepository
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.domain.repository.LiveMarketRepository
import com.fyp.basarattradeinvest.domain.repository.WatchlistRepository
import com.fyp.basarattradeinvest.domain.repository.AlertsRepository
import com.fyp.basarattradeinvest.data.repository.AlertsRepositoryImpl
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Locale

sealed interface RecommendationCardUiState {
    data object Idle : RecommendationCardUiState
    data class Loading(val symbol: String) : RecommendationCardUiState
    data class Success(val symbol: String, val detail: RecommendationDetail) : RecommendationCardUiState
    data class Error(val symbol: String) : RecommendationCardUiState
}

sealed interface WatchlistFavoriteUiState {
    data object Loading : WatchlistFavoriteUiState
    data object NotSaved : WatchlistFavoriteUiState
    data class Saved(val watchlistIds: List<String>) : WatchlistFavoriteUiState
    data object Updating : WatchlistFavoriteUiState
    data object Error : WatchlistFavoriteUiState
}

sealed interface QuickAlertActionState {
    data object Idle : QuickAlertActionState
    data object Creating : QuickAlertActionState
    data class Success(val message: String) : QuickAlertActionState
    data class Error(val message: String) : QuickAlertActionState
}

class StockDetailViewModel(
    private val repository: StockRepository = StockRepositoryImpl(),
    private val recommendationsRepository: RecommendationsRepository = RecommendationsRepositoryImpl(),
    private val watchlistRepository: WatchlistRepository = NetworkClient.watchlistRepository,
    private val alertsRepository: AlertsRepository = AlertsRepositoryImpl(),
    private val liveMarketRepository: LiveMarketRepository = NetworkClient.liveMarketRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<StockDetailUiState>(StockDetailUiState.Loading)
    val uiState: StateFlow<StockDetailUiState> = _uiState.asStateFlow()

    private var currentSymbol: String = ""
    private val liveSubscriptionOwner = "stock-detail-${System.identityHashCode(this)}"
    private var isLiveUpdatesActive = false
    private var currentTimeframe: String = "1M"
    private var currentSection: String = "Quotes"
    private var currentSubPill: String = "By Price"
    private var lastSuccessfulFetchAt: Long = 0L
    private val _recommendationCardState = MutableStateFlow<RecommendationCardUiState>(RecommendationCardUiState.Idle)
    val recommendationCardState: StateFlow<RecommendationCardUiState> = _recommendationCardState.asStateFlow()
    private var recommendationCardSymbol: String? = null
    private var recommendationCardLoadingSymbol: String? = null
    private var recommendationCardJob: kotlinx.coroutines.Job? = null
    private val freshnessWindowMs = 5 * 60 * 1000L
    private val _watchlistFavoriteState = MutableStateFlow<WatchlistFavoriteUiState>(WatchlistFavoriteUiState.Loading)
    val watchlistFavoriteState: StateFlow<WatchlistFavoriteUiState> = _watchlistFavoriteState.asStateFlow()
    private val _watchlistMessages = MutableSharedFlow<String>(extraBufferCapacity = 1)
    val watchlistMessages: SharedFlow<String> = _watchlistMessages
    private var checkedWatchlistSymbol: String? = null
    private val _quickAlertActionState = MutableStateFlow<QuickAlertActionState>(QuickAlertActionState.Idle)
    val quickAlertActionState: StateFlow<QuickAlertActionState> = _quickAlertActionState.asStateFlow()

    init {
        viewModelScope.launch {
            liveMarketRepository.quoteUpdates.collect { quote ->
                val current = _uiState.value as? StockDetailUiState.Success ?: return@collect
                if (!quote.symbol.equals(current.detail.symbol, ignoreCase = true)) return@collect
                _uiState.value = current.copy(
                    livePrice = quote.current,
                    liveChange = quote.change,
                    liveChangePct = quote.changePct,
                    liveVolume = quote.volume,
                    isLivePriceStreaming = quote.source == LiveQuoteSource.WEBSOCKET,
                    liveIsStale = quote.isStale
                )
            }
        }
        viewModelScope.launch {
            liveMarketRepository.connectionState.collect { connectionState ->
                val current = _uiState.value as? StockDetailUiState.Success ?: return@collect
                _uiState.value = current.copy(wsConnectionState = connectionState)
            }
        }
        // The heart must follow watchlist edits made on other screens; without this the
        // detail page keeps showing the membership it checked on first entry.
        viewModelScope.launch {
            watchlistRepository.watchlistUpdates.collect { watchlist ->
                val symbol = checkedWatchlistSymbol ?: return@collect
                val isSaved = watchlist.items.any { it.symbol.equals(symbol, ignoreCase = true) }
                _watchlistFavoriteState.value = if (isSaved) {
                    WatchlistFavoriteUiState.Saved(listOf(watchlist.id))
                } else WatchlistFavoriteUiState.NotSaved
            }
        }
    }

    fun setLiveUpdatesActive(active: Boolean) {
        isLiveUpdatesActive = active
        val symbols = if (active && currentSymbol.isNotBlank()) listOf(currentSymbol) else emptyList()
        liveMarketRepository.setSubscriptions(liveSubscriptionOwner, symbols)
        if (active) {
            liveMarketRepository.getCachedQuote(currentSymbol)?.let(::applyLiveQuote)
        }
    }

    private fun applyLiveQuote(quote: LiveQuote) {
        val current = _uiState.value as? StockDetailUiState.Success ?: return
        if (!quote.symbol.equals(current.detail.symbol, ignoreCase = true)) return
        _uiState.value = current.copy(
            livePrice = quote.current,
            liveChange = quote.change,
            liveChangePct = quote.changePct,
            liveVolume = quote.volume,
            isLivePriceStreaming = quote.source == LiveQuoteSource.WEBSOCKET,
            liveIsStale = quote.isStale
        )
    }

    fun ensureLoaded(symbol: String) {
        val requested = symbol.trim().uppercase()
        if (isLiveUpdatesActive) {
            liveMarketRepository.setSubscriptions(liveSubscriptionOwner, listOf(requested))
        }
        ensureWatchlistMembership(symbol)
        val state = _uiState.value
        // Compare against the symbol the cached state actually holds. This VM is
        // activity-scoped, so a Success state from a previously-opened stock must NOT
        // be mistaken for the requested one.
        val isSameSymbol = state is StockDetailUiState.Success &&
            state.detail.symbol.equals(requested, ignoreCase = true)
        currentSymbol = requested
        val shouldLoad = !isSameSymbol || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
        if (shouldLoad) {
            loadStock(symbol)
        }
    }

    fun loadStock(symbol: String, forceRefresh: Boolean = false) {
        if (currentSymbol != symbol) {
            _quickAlertActionState.value = QuickAlertActionState.Idle
        }
        currentSymbol = symbol
        viewModelScope.launch {
            val currentState = _uiState.value
            val isSameSymbol = currentState is StockDetailUiState.Success &&
                currentState.detail.symbol.equals(symbol, ignoreCase = true)
            if (!forceRefresh && isSameSymbol && System.currentTimeMillis() - lastSuccessfulFetchAt <= freshnessWindowMs) {
                return@launch
            }
            _uiState.value = StockDetailUiState.Loading

            coroutineScope {
                val detailDeferred = async { repository.getStockOverview(symbol) }
                val chartDeferred = async { repository.getPriceHistory(symbol, currentTimeframe) }
                val tradesDeferred = async { repository.getRecentTrades(symbol) }

                val detailResult = detailDeferred.await()
                var candles = chartDeferred.await().getOrDefault(emptyList())
                val trades = tradesDeferred.await().getOrDefault(emptyList())

                // If default timeframe returned empty candles, attempt fallback to 1M or 1Y if available
                if (candles.isEmpty() && currentTimeframe != "1M") {
                    val fallback = repository.getPriceHistory(symbol, "1M").getOrDefault(emptyList())
                    if (fallback.isNotEmpty()) {
                        candles = fallback
                        currentTimeframe = "1M"
                    }
                }

                if (detailResult.isSuccess) {
                    val detail = detailResult.getOrThrow()
                    lastSuccessfulFetchAt = System.currentTimeMillis()

                    _uiState.value = StockDetailUiState.Success(
                        detail = detail,
                        candles = candles,
                        trades = trades,
                        selectedTimeframe = currentTimeframe,
                        selectedSection = currentSection,
                        selectedSubPill = currentSubPill
                    )
                } else {
                    _uiState.value = StockDetailUiState.Error("Unable to load stock details for $symbol")
                }
            }
        }
    }

    fun createQuickAlert() {
        if (_quickAlertActionState.value is QuickAlertActionState.Creating) return

        val symbol = currentSymbol.trim().uppercase(Locale.ROOT)
        if (symbol.isBlank()) {
            _quickAlertActionState.value = QuickAlertActionState.Error("Stock symbol is unavailable")
            return
        }

        _quickAlertActionState.value = QuickAlertActionState.Creating
        viewModelScope.launch {
            val result = alertsRepository.createQuickAlertRule(symbol)
            _quickAlertActionState.value = result.fold(
                onSuccess = { QuickAlertActionState.Success(it.message.ifBlank { "Price alert created" }) },
                onFailure = {
                    QuickAlertActionState.Error(it.message ?: "Unable to create price alert. Please try again.")
                }
            )
        }
    }

    fun clearQuickAlertActionState() {
        _quickAlertActionState.value = QuickAlertActionState.Idle
    }

    fun setTimeframe(timeframe: String) {
        if (currentTimeframe == timeframe) return
        currentTimeframe = timeframe
        viewModelScope.launch {
            val currentState = _uiState.value
            if (currentState is StockDetailUiState.Success) {
                val chartResult = repository.getPriceHistory(currentSymbol, timeframe)
                val candles = chartResult.getOrDefault(emptyList())
                _uiState.value = currentState.copy(
                    candles = candles,
                    selectedTimeframe = timeframe
                )
            }
        }
    }

    fun setSection(section: String) {
        currentSection = section
        // Reset sub-pill to first option when switching sections
        currentSubPill = when (section) {
            "Quotes" -> "By Price"
            "News" -> "Latest"
            "Profile" -> "Overview"
            else -> "By Price"
        }
        val currentState = _uiState.value
        if (currentState is StockDetailUiState.Success) {
            _uiState.value = currentState.copy(
                selectedSection = currentSection,
                selectedSubPill = currentSubPill
            )
        }
    }

    fun setSubPill(pill: String) {
        currentSubPill = pill
        val currentState = _uiState.value
        if (currentState is StockDetailUiState.Success) {
            _uiState.value = currentState.copy(selectedSubPill = pill)
        }
    }

    fun ensureWatchlistMembership(symbol: String) {
        val normalized = symbol.trim().uppercase()
        if (normalized.isEmpty() || checkedWatchlistSymbol == normalized) return
        checkedWatchlistSymbol = normalized
        _watchlistFavoriteState.value = WatchlistFavoriteUiState.Loading
        viewModelScope.launch {
            watchlistRepository.checkSymbol(normalized).fold(
                onSuccess = { membership ->
                    _watchlistFavoriteState.value = if (membership.isInWatchlist) {
                        WatchlistFavoriteUiState.Saved(membership.watchlistIds)
                    } else WatchlistFavoriteUiState.NotSaved
                },
                onFailure = {
                    checkedWatchlistSymbol = null
                    _watchlistFavoriteState.value = WatchlistFavoriteUiState.Error
                }
            )
        }
    }

    fun toggleWatchlist(symbol: String) {
        val normalized = symbol.trim().uppercase()
        when (val state = _watchlistFavoriteState.value) {
            is WatchlistFavoriteUiState.Saved -> {
                if (state.watchlistIds.isEmpty()) {
                    checkedWatchlistSymbol = null
                    ensureWatchlistMembership(normalized)
                    return
                }
                _watchlistFavoriteState.value = WatchlistFavoriteUiState.Updating
                viewModelScope.launch {
                    watchlistRepository.removeFromWatchlists(normalized, state.watchlistIds).fold(
                        onSuccess = {
                            _watchlistFavoriteState.value = WatchlistFavoriteUiState.NotSaved
                            _watchlistMessages.emit("Removed from watchlist")
                        },
                        onFailure = { error ->
                            watchlistRepository.checkSymbol(normalized).fold(
                                onSuccess = { membership ->
                                    _watchlistFavoriteState.value = if (membership.isInWatchlist) {
                                        WatchlistFavoriteUiState.Saved(membership.watchlistIds)
                                    } else WatchlistFavoriteUiState.NotSaved
                                },
                                onFailure = { _watchlistFavoriteState.value = state }
                            )
                            _watchlistMessages.emit(error.message ?: "Unable to update watchlist")
                        }
                    )
                }
            }
            WatchlistFavoriteUiState.NotSaved -> {
                _watchlistFavoriteState.value = WatchlistFavoriteUiState.Updating
                viewModelScope.launch {
                    watchlistRepository.addToDefaultWatchlist(normalized).fold(
                        onSuccess = { watchlist ->
                            _watchlistFavoriteState.value = WatchlistFavoriteUiState.Saved(listOf(watchlist.id))
                            _watchlistMessages.emit("Added to watchlist")
                        },
                        onFailure = { error ->
                            _watchlistFavoriteState.value = WatchlistFavoriteUiState.NotSaved
                            _watchlistMessages.emit(error.message ?: "Unable to update watchlist")
                        }
                    )
                }
            }
            WatchlistFavoriteUiState.Error -> ensureWatchlistMembership(normalized)
            WatchlistFavoriteUiState.Loading, WatchlistFavoriteUiState.Updating -> Unit
        }
    }

    /** Kept for source compatibility; the detail screen no longer requests or renders this card. */
    fun loadRecommendationCard(symbol: String, knownPrice: Double? = null) {
        val normalizedSymbol = symbol.trim().uppercase()
        if (normalizedSymbol.isEmpty()) return

        RecommendationsRepositoryImpl.getCachedRecommendationDetail(normalizedSymbol)?.let { cached ->
            recommendationCardSymbol = normalizedSymbol
            recommendationCardLoadingSymbol = null
            recommendationCardJob?.cancel()
            _recommendationCardState.value = RecommendationCardUiState.Success(normalizedSymbol, cached)
            return
        }

        if (recommendationCardSymbol == normalizedSymbol) recommendationCardSymbol = null
        if (recommendationCardLoadingSymbol == normalizedSymbol) return

        recommendationCardJob?.cancel()
        recommendationCardLoadingSymbol = normalizedSymbol
        _recommendationCardState.value = RecommendationCardUiState.Loading(normalizedSymbol)
        recommendationCardJob = viewModelScope.launch {
            try {
                val result = recommendationsRepository.getRecommendationDetail(normalizedSymbol, knownPrice)
                if (recommendationCardLoadingSymbol != normalizedSymbol) return@launch
                result.fold(
                    onSuccess = { detail ->
                        recommendationCardSymbol = normalizedSymbol
                        _recommendationCardState.value = RecommendationCardUiState.Success(normalizedSymbol, detail)
                    },
                    onFailure = {
                        recommendationCardSymbol = null
                        _recommendationCardState.value = RecommendationCardUiState.Error(normalizedSymbol)
                    }
                )
            } catch (cancelled: kotlinx.coroutines.CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                if (recommendationCardLoadingSymbol == normalizedSymbol) {
                    recommendationCardSymbol = null
                    _recommendationCardState.value = RecommendationCardUiState.Error(normalizedSymbol)
                }
            } finally {
                if (recommendationCardLoadingSymbol == normalizedSymbol) {
                    recommendationCardLoadingSymbol = null
                }
            }
        }
    }

    fun retry() {
        if (currentSymbol.isNotEmpty()) {
            loadStock(currentSymbol)
        }
    }

    override fun onCleared() {
        liveMarketRepository.setSubscriptions(liveSubscriptionOwner, emptyList())
        super.onCleared()
    }
}
