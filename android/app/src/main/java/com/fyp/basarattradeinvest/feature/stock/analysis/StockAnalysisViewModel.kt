package com.fyp.basarattradeinvest.feature.stock.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.mapper.ForecastDtoMapper
import com.fyp.basarattradeinvest.data.repository.ForecastRepositoryImpl
import com.fyp.basarattradeinvest.data.repository.SentimentRepositoryImpl
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.ForecastRepository
import com.fyp.basarattradeinvest.domain.repository.SentimentRepository
import com.fyp.basarattradeinvest.domain.repository.StockRepository
import com.fyp.basarattradeinvest.domain.usecase.forecast.GetForecastHistoryUseCase
import com.fyp.basarattradeinvest.domain.usecase.forecast.GetStockForecastUseCase
import com.fyp.basarattradeinvest.domain.usecase.sentiment.GetSentimentHistoryUseCase
import com.fyp.basarattradeinvest.domain.usecase.sentiment.GetSentimentNewsUseCase
import com.fyp.basarattradeinvest.domain.usecase.sentiment.GetStockSentimentUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class StockAnalysisViewModel(
    private val repository: StockRepository = StockRepositoryImpl(),
    private val forecastRepository: ForecastRepository = ForecastRepositoryImpl(),
    private val sentimentRepository: SentimentRepository = SentimentRepositoryImpl(),
    private val getStockForecastUseCase: GetStockForecastUseCase = GetStockForecastUseCase(forecastRepository),
    private val getForecastHistoryUseCase: GetForecastHistoryUseCase = GetForecastHistoryUseCase(forecastRepository),
    private val getStockSentimentUseCase: GetStockSentimentUseCase = GetStockSentimentUseCase(sentimentRepository),
    private val getSentimentHistoryUseCase: GetSentimentHistoryUseCase = GetSentimentHistoryUseCase(sentimentRepository),
    private val getSentimentNewsUseCase: GetSentimentNewsUseCase = GetSentimentNewsUseCase(sentimentRepository)
) : ViewModel() {

    private val _uiState = MutableStateFlow<StockAnalysisUiState>(StockAnalysisUiState.Loading)
    val uiState: StateFlow<StockAnalysisUiState> = _uiState.asStateFlow()

    private var currentSymbol: String = ""
    private var currentTab: AnalysisTab = AnalysisTab.TECHNICAL
    private var currentHorizon: String = "1W"
    private var currentPriceRange: String = "1M"
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L

    fun ensureLoaded(symbol: String) {
        val state = _uiState.value
        val isSameSymbol = currentSymbol == symbol && state is StockAnalysisUiState.Success
        val shouldLoad = !isSameSymbol || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
        if (shouldLoad) {
            loadAnalysis(symbol)
        }
    }

    fun loadAnalysis(symbol: String) {
        viewModelScope.launch {
            val currentState = _uiState.value
            val isSameSymbol = currentState is StockAnalysisUiState.Success &&
                currentState.analysis.symbol.equals(symbol, ignoreCase = true)
            if (isSameSymbol && System.currentTimeMillis() - lastSuccessfulFetchAt <= freshnessWindowMs) {
                return@launch
            }
            currentSymbol = symbol
            _uiState.value = StockAnalysisUiState.Loading

            val result = repository.getStockAnalysis(symbol)
            if (result.isSuccess) {
                val analysis = result.getOrThrow()
                lastSuccessfulFetchAt = System.currentTimeMillis()
                _uiState.value = StockAnalysisUiState.Success(
                    analysis = analysis,
                    selectedTab = currentTab,
                    selectedPriceRange = currentPriceRange,
                    priceHistoryState = PriceHistorySectionState.Loading,
                    selectedHorizon = currentHorizon,
                    forecastState = ForecastSectionState.Loading,
                    historyState = ForecastHistorySectionState.Loading,
                    sentimentState = StockSentimentSectionState.Loading,
                    sentimentHistoryState = SentimentHistorySectionState.Loading,
                    sentimentNewsState = SentimentNewsSectionState.Loading
                )
                // Load price history chart for technical analysis
                loadPriceHistory(symbol, currentPriceRange)
                // Preload forecast data
                loadForecast(symbol, currentHorizon)
                loadForecastHistory(symbol, currentHorizon)
                // Preload sentiment data
                loadSentiment(symbol)
            } else {
                _uiState.value = StockAnalysisUiState.Error(
                    result.exceptionOrNull()?.message ?: "Unable to load stock analysis for $symbol"
                )
            }
        }
    }

    fun selectTab(tab: AnalysisTab) {
        if (currentTab == tab) return
        currentTab = tab
        val currentState = _uiState.value
        if (currentState is StockAnalysisUiState.Success) {
            _uiState.value = currentState.copy(selectedTab = tab)
            when (tab) {
                AnalysisTab.TECHNICAL -> {
                    if (currentState.priceHistoryState is PriceHistorySectionState.Error) {
                        loadPriceHistory(currentSymbol, currentPriceRange)
                    }
                }
                AnalysisTab.FORECAST -> {
                    if (currentState.forecastState is ForecastSectionState.Error || currentState.forecastState is ForecastSectionState.Loading) {
                        loadForecast(currentSymbol, currentHorizon)
                    }
                    if (currentState.historyState is ForecastHistorySectionState.Error || currentState.historyState is ForecastHistorySectionState.Loading) {
                        loadForecastHistory(currentSymbol, currentHorizon)
                    }
                }
                AnalysisTab.SENTIMENT -> {
                    if (currentState.sentimentState is StockSentimentSectionState.Error || currentState.sentimentState is StockSentimentSectionState.Loading) {
                        loadSentiment(currentSymbol)
                    }
                }
                AnalysisTab.FUNDAMENTALS -> {
                    // Already populated in analysis.fundamentals
                }
            }
        }
    }

    fun selectPriceRange(range: String) {
        if (currentPriceRange == range) return
        currentPriceRange = range
        val currentState = _uiState.value
        if (currentState is StockAnalysisUiState.Success) {
            _uiState.value = currentState.copy(
                selectedPriceRange = range,
                priceHistoryState = PriceHistorySectionState.Loading
            )
            loadPriceHistory(currentSymbol, range)
        }
    }

    fun retryPriceHistory() {
        if (currentSymbol.isNotEmpty()) {
            val currentState = _uiState.value
            if (currentState is StockAnalysisUiState.Success) {
                _uiState.value = currentState.copy(priceHistoryState = PriceHistorySectionState.Loading)
            }
            loadPriceHistory(currentSymbol, currentPriceRange)
        }
    }

    fun selectHorizon(horizon: String) {
        if (currentHorizon == horizon) return
        currentHorizon = horizon
        val currentState = _uiState.value
        if (currentState is StockAnalysisUiState.Success) {
            _uiState.value = currentState.copy(
                selectedHorizon = horizon,
                forecastState = ForecastSectionState.Loading,
                historyState = ForecastHistorySectionState.Loading
            )
            loadForecast(currentSymbol, horizon)
            loadForecastHistory(currentSymbol, horizon)
        }
    }

    fun retryForecast() {
        if (currentSymbol.isNotEmpty()) {
            val currentState = _uiState.value
            if (currentState is StockAnalysisUiState.Success) {
                _uiState.value = currentState.copy(forecastState = ForecastSectionState.Loading)
            }
            loadForecast(currentSymbol, currentHorizon)
        }
    }

    fun retryHistory() {
        if (currentSymbol.isNotEmpty()) {
            val currentState = _uiState.value
            if (currentState is StockAnalysisUiState.Success) {
                _uiState.value = currentState.copy(historyState = ForecastHistorySectionState.Loading)
            }
            loadForecastHistory(currentSymbol, currentHorizon)
        }
    }

    fun retrySentiment() {
        if (currentSymbol.isNotEmpty()) {
            val currentState = _uiState.value
            if (currentState is StockAnalysisUiState.Success) {
                _uiState.value = currentState.copy(
                    sentimentState = StockSentimentSectionState.Loading,
                    sentimentHistoryState = SentimentHistorySectionState.Loading,
                    sentimentNewsState = SentimentNewsSectionState.Loading
                )
            }
            loadSentiment(currentSymbol)
        }
    }

    private fun loadPriceHistory(symbol: String, range: String) {
        viewModelScope.launch {
            val result = repository.getPriceHistory(symbol, range)
            val currentState = _uiState.value
            if (currentState is StockAnalysisUiState.Success) {
                if (result.isSuccess) {
                    val candles = result.getOrThrow()
                    _uiState.value = currentState.copy(
                        priceHistoryState = if (candles.isEmpty()) {
                            PriceHistorySectionState.Empty
                        } else {
                            PriceHistorySectionState.Success(candles)
                        }
                    )
                } else {
                    _uiState.value = currentState.copy(
                        priceHistoryState = PriceHistorySectionState.Error(
                            result.exceptionOrNull()?.message ?: "Unable to load price history"
                        )
                    )
                }
            }
        }
    }

    private fun loadForecast(symbol: String, horizon: String) {
        viewModelScope.launch {
            val result = getStockForecastUseCase(symbol, horizon)
            val currentState = _uiState.value
            if (currentState is StockAnalysisUiState.Success) {
                if (result.isSuccess) {
                    val rawForecast = result.getOrThrow()
                    val livePrice = rawForecast.currentPrice ?: currentState.analysis.price
                    val forecast = ForecastDtoMapper.recalculateTargets(rawForecast, livePrice)
                    _uiState.value = currentState.copy(
                        forecastState = ForecastSectionState.Success(forecast)
                    )
                } else {
                    _uiState.value = currentState.copy(
                        forecastState = ForecastSectionState.Error(
                            result.exceptionOrNull()?.message ?: "Unable to load ML forecast"
                        )
                    )
                }
            }
        }
    }

    private fun loadForecastHistory(symbol: String, horizon: String) {
        viewModelScope.launch {
            val result = getForecastHistoryUseCase(symbol, horizon = horizon, limit = 30)
            val currentState = _uiState.value
            if (currentState is StockAnalysisUiState.Success) {
                if (result.isSuccess) {
                    val history = result.getOrThrow()
                    _uiState.value = currentState.copy(
                        historyState = if (history.history.isEmpty()) {
                            ForecastHistorySectionState.Empty
                        } else {
                            ForecastHistorySectionState.Success(history)
                        }
                    )
                } else {
                    _uiState.value = currentState.copy(
                        historyState = ForecastHistorySectionState.Error(
                            result.exceptionOrNull()?.message ?: "Unable to load forecast history"
                        )
                    )
                }
            }
        }
    }

    private fun loadSentiment(symbol: String) {
        viewModelScope.launch {
            // Fetch the three independent sentiment endpoints concurrently. Each child
            // updates only its own state slice; the read-modify-write is non-suspending
            // and runs on the main dispatcher, so concurrent updates never clobber.
            launch {
                val sentimentRes = getStockSentimentUseCase(symbol)
                val state = _uiState.value
                if (state is StockAnalysisUiState.Success) {
                    _uiState.value = if (sentimentRes.isSuccess) {
                        state.copy(
                            sentimentState = StockSentimentSectionState.Success(sentimentRes.getOrThrow())
                        )
                    } else {
                        state.copy(
                            sentimentState = StockSentimentSectionState.Error(
                                sentimentRes.exceptionOrNull()?.message ?: "Unable to load stock sentiment"
                            )
                        )
                    }
                }
            }

            launch {
                val historyRes = getSentimentHistoryUseCase(symbol, period = "1M")
                val state = _uiState.value
                if (state is StockAnalysisUiState.Success) {
                    _uiState.value = if (historyRes.isSuccess) {
                        val history = historyRes.getOrThrow()
                        state.copy(
                            sentimentHistoryState = if (history.data.isEmpty()) {
                                SentimentHistorySectionState.Empty
                            } else {
                                SentimentHistorySectionState.Success(history)
                            }
                        )
                    } else {
                        state.copy(
                            sentimentHistoryState = SentimentHistorySectionState.Error(
                                historyRes.exceptionOrNull()?.message ?: "Unable to load sentiment history"
                            )
                        )
                    }
                }
            }

            launch {
                val newsRes = getSentimentNewsUseCase(symbol, page = 1, limit = 15)
                val state = _uiState.value
                if (state is StockAnalysisUiState.Success) {
                    _uiState.value = if (newsRes.isSuccess) {
                        val newsPage = newsRes.getOrThrow()
                        state.copy(
                            sentimentNewsState = if (newsPage.items.isEmpty()) {
                                SentimentNewsSectionState.Empty
                            } else {
                                SentimentNewsSectionState.Success(newsPage.items)
                            }
                        )
                    } else {
                        state.copy(
                            sentimentNewsState = SentimentNewsSectionState.Error(
                                newsRes.exceptionOrNull()?.message ?: "Unable to load sentiment news"
                            )
                        )
                    }
                }
            }
        }
    }

    fun retry() {
        if (currentSymbol.isNotEmpty()) {
            loadAnalysis(currentSymbol)
        }
    }
}
