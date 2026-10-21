package com.fyp.basarattradeinvest.feature.markets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.core.session.AuthState
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.repository.MarketRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.market.IndexConstituent
import com.fyp.basarattradeinvest.domain.model.market.IndexConstituents
import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.model.stock.SymbolFilterType
import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import com.fyp.basarattradeinvest.domain.repository.LiveMarketRepository
import com.fyp.basarattradeinvest.domain.repository.MarketRepository
import com.fyp.basarattradeinvest.domain.usecase.market.GetMarketIndicesUseCase
import com.fyp.basarattradeinvest.domain.usecase.market.GetSectorPerformancesUseCase
import com.fyp.basarattradeinvest.domain.usecase.market.GetKmi30ConstituentsUseCase
import com.fyp.basarattradeinvest.domain.usecase.market.GetKse100ConstituentsUseCase
import com.fyp.basarattradeinvest.domain.usecase.market.GetKse30ConstituentsUseCase
import com.fyp.basarattradeinvest.domain.usecase.market.GetTopGainersUseCase
import com.fyp.basarattradeinvest.domain.usecase.market.GetTopLosersUseCase
import com.fyp.basarattradeinvest.domain.usecase.market.GetVolumeSpikesUseCase
import kotlinx.coroutines.async
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MarketDashboardViewModel(
    private val repository: MarketRepository = MarketRepositoryImpl(),
    private val getMarketIndicesUseCase: GetMarketIndicesUseCase = GetMarketIndicesUseCase(repository),
    private val getTopGainersUseCase: GetTopGainersUseCase = GetTopGainersUseCase(repository),
    private val getTopLosersUseCase: GetTopLosersUseCase = GetTopLosersUseCase(repository),
    private val getVolumeSpikesUseCase: GetVolumeSpikesUseCase = GetVolumeSpikesUseCase(repository),
    private val getKse100ConstituentsUseCase: GetKse100ConstituentsUseCase = GetKse100ConstituentsUseCase(repository),
    private val getKse30ConstituentsUseCase: GetKse30ConstituentsUseCase = GetKse30ConstituentsUseCase(repository),
    private val getKmi30ConstituentsUseCase: GetKmi30ConstituentsUseCase = GetKmi30ConstituentsUseCase(repository),
    private val getSectorPerformancesUseCase: GetSectorPerformancesUseCase = GetSectorPerformancesUseCase(repository),
    private val liveMarketRepository: LiveMarketRepository = NetworkClient.liveMarketRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<MarketDashboardUiState>(MarketDashboardUiState.Loading)
    val uiState: StateFlow<MarketDashboardUiState> = _uiState.asStateFlow()

    private var currentSelection = MarketListSelection.GAINERS
    // Switching chips re-reads from here so a known list paints immediately instead of waiting
    // on another round trip; refresh drops it so the next read is live.
    private val rowCache = mutableMapOf<MarketListSelection, List<MarketStock>>()
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L
    private var isMarketDataLoading = false
    private var isLiveUpdatesActive = false
    private var accountGeneration = 0
    private var currentAccountKey: String? = accountKeyForCurrentSession()
    private var marketDataJob: Job? = null
    private var rowsJob: Job? = null
    private val pendingQuotes = mutableMapOf<String, LiveQuote>()
    private var quoteFlushJob: Job? = null

    init {
        // Quote ticks arrive one per symbol, so a single market snapshot would otherwise emit
        // ~110 states. Accumulate them and publish one update per flush window instead.
        viewModelScope.launch {
            liveMarketRepository.quoteUpdates.collect { quote ->
                pendingQuotes[quote.symbol.uppercase()] = quote
                if (quoteFlushJob?.isActive != true) {
                    quoteFlushJob = viewModelScope.launch {
                        delay(QUOTE_FLUSH_INTERVAL_MS)
                        applyPendingQuotes()
                    }
                }
            }
        }

        // Collect connection state → update wsConnectionState in Success state
        viewModelScope.launch {
            liveMarketRepository.connectionState.collect { connState ->
                val current = _uiState.value as? MarketDashboardUiState.Success ?: return@collect
                _uiState.value = current.copy(wsConnectionState = connState)
            }
        }

        viewModelScope.launch {
            SessionManager.authState.collect { authState ->
                val nextAccountKey = accountKeyFor(authState)
                if (nextAccountKey == currentAccountKey) return@collect

                currentAccountKey = nextAccountKey
                accountGeneration++
                marketDataJob?.cancel()
                marketDataJob = null
                rowsJob?.cancel()
                rowsJob = null
                pendingQuotes.clear()
                quoteFlushJob?.cancel()
                quoteFlushJob = null
                isMarketDataLoading = false
                lastSuccessfulFetchAt = 0L
                currentSelection = MarketListSelection.GAINERS
                rowCache.clear()
                _uiState.value = MarketDashboardUiState.Loading
                updateMarketSubscriptions()

                if (nextAccountKey != null) {
                    loadMarketData(isRefresh = true)
                }
            }
        }

        ensureLoaded()
    }

    fun ensureLoaded() {
        val state = _uiState.value
        val shouldLoad = state !is MarketDashboardUiState.Success || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
        if (shouldLoad) {
            loadMarketData(isRefresh = false)
        }
    }

    fun loadMarketData(isRefresh: Boolean = false) {
        if (isMarketDataLoading) return
        isMarketDataLoading = true
        if (isRefresh) rowCache.clear()
        val loadGeneration = accountGeneration
        marketDataJob = viewModelScope.launch {
            try {
                val currentState = _uiState.value
                val hasUsableData = currentState is MarketDashboardUiState.Success
                val shouldSkip = !isRefresh && hasUsableData && System.currentTimeMillis() - lastSuccessfulFetchAt <= freshnessWindowMs
                if (shouldSkip) return@launch
                if (!isRefresh && !hasUsableData) {
                    _uiState.value = MarketDashboardUiState.Loading
                }

                val indicesDeferred = async { getMarketIndicesUseCase() }
                val rowsDeferred = async { fetchRows(currentSelection) }
                val sectorsDeferred = async { getSectorPerformancesUseCase() }
                val sessionDeferred = async { liveMarketRepository.getMarketSessionStatus() }

                // Await only the above-the-fold data first so the dashboard paints as soon as
                // indices and the selected symbol list are ready. Sectors are secondary and
                // fill in progressively below.
                val indicesResult = indicesDeferred.await()
                val rowsResult = rowsDeferred.await()
                val marketSession = sessionDeferred.await().getOrNull()
                if (loadGeneration != accountGeneration) return@launch

                if (indicesResult.isSuccess || rowsResult.isSuccess) {
                    val indices = indicesResult.getOrDefault(emptyList())
                    val rows = rowsResult.getOrDefault(emptyList())
                    if (rowsResult.isSuccess) rowCache[currentSelection] = rows

                    val currentTime = SimpleDateFormat("HH:mm", Locale.US).format(Date())
                    lastSuccessfulFetchAt = System.currentTimeMillis()

                    _uiState.value = MarketDashboardUiState.Success(
                        indices = indices,
                        rows = applyCachedMarketStocks(rows),
                        selection = currentSelection,
                        sectors = emptyList(),
                        lastUpdated = currentTime,
                        liveQuotes = liveMarketRepository.quoteCache.value,
                        wsConnectionState = liveMarketRepository.connectionState.value,
                        marketSession = marketSession
                    )
                    updateMarketSubscriptions()

                    // Secondary section: fill in once it arrives without blocking first paint.
                    val sectors = sectorsDeferred.await().getOrDefault(emptyList())
                    if (loadGeneration != accountGeneration) return@launch
                    val stateAfterSecondary = _uiState.value
                    if (stateAfterSecondary is MarketDashboardUiState.Success) {
                        _uiState.value = stateAfterSecondary.copy(sectors = sectors)
                    }
                } else {
                    val errorMsg = indicesResult.exceptionOrNull()?.message
                        ?: rowsResult.exceptionOrNull()?.message
                        ?: "Unable to load market data. Please check connection."
                    _uiState.value = MarketDashboardUiState.Error(errorMsg)
                }
            } finally {
                if (loadGeneration == accountGeneration) {
                    isMarketDataLoading = false
                    marketDataJob = null
                }
            }
        }
    }

    fun refreshData() {
        loadMarketData(isRefresh = true)
    }

    private fun applyPendingQuotes() {
        quoteFlushJob = null
        if (pendingQuotes.isEmpty()) return
        val batch = pendingQuotes.toMap()
        pendingQuotes.clear()
        val current = _uiState.value as? MarketDashboardUiState.Success ?: return
        val quoteFor: (String) -> LiveQuote? = { symbol -> batch[symbol.uppercase()] }
        val quotes = current.liveQuotes.toMutableMap()
        quotes.putAll(batch)
        val updatedRows = current.rows.map { stock ->
            quoteFor(stock.symbol)?.let { stock.withQuote(it) } ?: stock
        }
        if (current.selection in rowCache) rowCache[current.selection] = updatedRows
        _uiState.value = current.copy(
            liveQuotes = quotes,
            rows = updatedRows
        )
    }

    fun setLiveUpdatesActive(active: Boolean) {
        if (isLiveUpdatesActive == active) return
        isLiveUpdatesActive = active
        updateMarketSubscriptions()
    }

    private fun updateMarketSubscriptions() {
        val state = _uiState.value as? MarketDashboardUiState.Success
        val symbols = if (isLiveUpdatesActive) {
            state?.rows.orEmpty().map { it.symbol }.toSet()
        } else {
            emptySet()
        }
        liveMarketRepository.setSubscriptions("markets", symbols)
    }

    fun setSelection(selection: MarketListSelection) {
        if (currentSelection == selection && _uiState.value is MarketDashboardUiState.Success) return
        currentSelection = selection
        rowsJob?.cancel()

        val cached = rowCache[selection]
        val stateBefore = _uiState.value
        if (stateBefore is MarketDashboardUiState.Success) {
            _uiState.value = if (cached != null) {
                stateBefore.copy(
                    selection = selection,
                    rows = cached,
                    isRowsLoading = false
                )
            } else {
                // Blank the table instead of leaving the previous selection's rows on screen
                // under the new chip's label while the cold fetch runs.
                stateBefore.copy(
                    selection = selection,
                    rows = emptyList(),
                    isRowsLoading = true
                )
            }
        }
        if (cached != null) {
            updateMarketSubscriptions()
            return
        }

        rowsJob = viewModelScope.launch {
            val requestGeneration = accountGeneration
            val result = fetchRows(selection)
            if (requestGeneration != accountGeneration || currentSelection != selection) return@launch
            val rows = result.getOrDefault(emptyList())
            if (result.isSuccess) rowCache[selection] = rows
            val currentState = _uiState.value
            if (currentState is MarketDashboardUiState.Success) {
                _uiState.value = currentState.copy(
                    selection = selection,
                    rows = applyCachedMarketStocks(rows),
                    isRowsLoading = false
                )
            }
            updateMarketSubscriptions()
        }
    }

    private suspend fun fetchRows(selection: MarketListSelection): Result<List<MarketStock>> = when (selection) {
        MarketListSelection.GAINERS -> getTopGainersUseCase(ROW_LIMIT)
        MarketListSelection.LOSERS -> getTopLosersUseCase(ROW_LIMIT)
        MarketListSelection.VOLUME_SPIKES -> getVolumeSpikesUseCase(ROW_LIMIT)
        // The repository's top-movers branch reads the real most-active list; reusing the
        // volume-spikes use case here would make two chips show identical rows.
        MarketListSelection.MOST_ACTIVE -> repository.getTopSymbols(SymbolFilterType.MOST_ACTIVE)
        MarketListSelection.KSE_100 -> fetchConstituentRows { getKse100ConstituentsUseCase() }
        MarketListSelection.KSE_30 -> fetchConstituentRows { getKse30ConstituentsUseCase() }
        MarketListSelection.KMI_30 -> fetchConstituentRows { getKmi30ConstituentsUseCase() }
    }

    private suspend fun fetchConstituentRows(
        load: suspend () -> Result<IndexConstituents>
    ): Result<List<MarketStock>> = load().map { constituents ->
        constituents.constituents.mapIndexed { index, constituent ->
            constituent.toMarketStock(index + 1)
        }
    }

    private fun IndexConstituent.toMarketStock(rank: Int) = MarketStock(
        rank = rank,
        symbol = symbol,
        companyName = name,
        sectorCode = if (weightPct > 0.0) {
            "$name \u2022 Wt: ${String.format(Locale.US, "%.2f", weightPct)}%"
        } else {
            name
        },
        price = current,
        change = change,
        changePercent = changePct,
        volume = if (volume > 0L) volume.toString() else ""
    )

    private fun applyCachedMarketStocks(stocks: List<MarketStock>): List<MarketStock> = stocks.map { stock ->
        liveMarketRepository.getCachedQuote(stock.symbol)?.let { quote -> stock.withQuote(quote) } ?: stock
    }

    private fun MarketStock.withQuote(quote: LiveQuote) = copy(
        price = quote.current ?: price,
        change = quote.change ?: change,
        changePercent = quote.changePct ?: changePercent,
        volume = quote.volume?.toString() ?: volume
    )

    private fun accountKeyForCurrentSession(): String? = accountKeyFor(SessionManager.authState.value)

    private fun accountKeyFor(authState: AuthState): String? = (authState as? AuthState.Authenticated)
        ?.let {
            SessionManager.getCurrentUserId()?.takeIf(String::isNotBlank)
                ?: it.userEmail.takeIf(String::isNotBlank)
        }
        ?.lowercase()

    companion object {
        private const val QUOTE_FLUSH_INTERVAL_MS = 750L
        private const val ROW_LIMIT = 10
    }
}
