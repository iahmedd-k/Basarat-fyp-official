package com.fyp.basarattradeinvest.feature.sentiment

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.SentimentRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.sentiment.GetMarketSentimentOverviewUseCase
import com.fyp.basarattradeinvest.domain.usecase.sentiment.GetSentimentHistoryUseCase
import com.fyp.basarattradeinvest.domain.usecase.sentiment.GetSentimentNewsUseCase
import com.fyp.basarattradeinvest.domain.usecase.sentiment.GetStockSentimentUseCase
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * SentimentViewModel
 *
 * Owns the complete SentimentScreenState.
 * Each of the 4 API sections loads independently — one failure does not
 * prevent other sections from displaying successful data.
 *
 * News pagination: call loadMoreNews() to append next page.
 * History period: call selectPeriod(period) to reload with a new period.
 */
class SentimentViewModel : ViewModel() {

    // ─── Use Cases (wired to shared SentimentRepositoryImpl) ────────────────

    private val repository = SentimentRepositoryImpl()
    private val getStockSentiment = GetStockSentimentUseCase(repository)
    private val getSentimentHistory = GetSentimentHistoryUseCase(repository)
    private val getSentimentNews = GetSentimentNewsUseCase(repository)
    private val getMarketSentimentOverview = GetMarketSentimentOverviewUseCase(repository)

    // ─── State ───────────────────────────────────────────────────────────────

    private val _uiState = MutableStateFlow(SentimentScreenState())
    val uiState: StateFlow<SentimentScreenState> = _uiState.asStateFlow()

    private var currentSymbol: String = ""
    private val newsPageSize = 20

    // ─── Entry Point ─────────────────────────────────────────────────────────

    /**
     * Load all 4 sections concurrently for the given symbol.
     * Safe to call multiple times (re-fetches all data).
     */
    fun loadAll(symbol: String) {
        currentSymbol = symbol
        _uiState.update { it.copy(symbol = symbol) }
        loadMarketSentiment()
        loadStockSentiment(symbol)
        loadHistory(symbol, _uiState.value.selectedPeriod)
        loadNews(symbol, page = 1, reset = true)
    }

    // ─── Market Sentiment ────────────────────────────────────────────────────

    private fun loadMarketSentiment() {
        viewModelScope.launch {
            _uiState.update { it.copy(marketSentiment = MarketSentimentSectionState.Loading) }
            getMarketSentimentOverview().fold(
                onSuccess = { data ->
                    _uiState.update {
                        it.copy(marketSentiment = MarketSentimentSectionState.Success(data))
                    }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(marketSentiment = MarketSentimentSectionState.Error(
                            e.message ?: "Unable to load market sentiment."
                        ))
                    }
                }
            )
        }
    }

    fun retryMarketSentiment() {
        loadMarketSentiment()
    }

    // ─── Stock Sentiment ─────────────────────────────────────────────────────

    private fun loadStockSentiment(symbol: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(stockSentiment = StockSentimentSectionState.Loading) }
            getStockSentiment(symbol).fold(
                onSuccess = { data ->
                    _uiState.update {
                        it.copy(stockSentiment = StockSentimentSectionState.Success(data))
                    }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(stockSentiment = StockSentimentSectionState.Error(
                            e.message ?: "Unable to load sentiment data."
                        ))
                    }
                }
            )
        }
    }

    fun retryStockSentiment() {
        if (currentSymbol.isNotEmpty()) loadStockSentiment(currentSymbol)
    }

    // ─── Sentiment History ───────────────────────────────────────────────────

    private fun loadHistory(symbol: String, period: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(history = SentimentHistorySectionState.Loading) }
            getSentimentHistory(symbol, period = period).fold(
                onSuccess = { data ->
                    if (data.data.isEmpty()) {
                        _uiState.update { it.copy(history = SentimentHistorySectionState.Empty) }
                    } else {
                        _uiState.update {
                            it.copy(history = SentimentHistorySectionState.Success(data))
                        }
                    }
                },
                onFailure = { e ->
                    _uiState.update {
                        it.copy(history = SentimentHistorySectionState.Error(
                            e.message ?: "Unable to load sentiment history."
                        ))
                    }
                }
            )
        }
    }

    fun selectPeriod(period: String) {
        if (period == _uiState.value.selectedPeriod) return
        _uiState.update { it.copy(selectedPeriod = period) }
        if (currentSymbol.isNotEmpty()) loadHistory(currentSymbol, period)
    }

    fun retryHistory() {
        if (currentSymbol.isNotEmpty()) loadHistory(currentSymbol, _uiState.value.selectedPeriod)
    }

    // ─── Sentiment News ──────────────────────────────────────────────────────

    /**
     * @param reset true for first page / retry (clears existing items)
     */
    private fun loadNews(symbol: String, page: Int, reset: Boolean) {
        viewModelScope.launch {
            if (reset) {
                _uiState.update { it.copy(news = SentimentNewsSectionState.Loading) }
            } else {
                // Append mode — show loading-more indicator
                val current = _uiState.value.news
                if (current is SentimentNewsSectionState.Success) {
                    _uiState.update {
                        it.copy(news = current.copy(isLoadingMore = true))
                    }
                }
            }

            getSentimentNews(symbol, page = page, limit = newsPageSize).fold(
                onSuccess = { newsPage ->
                    val existing = if (!reset && _uiState.value.news is SentimentNewsSectionState.Success) {
                        (_uiState.value.news as SentimentNewsSectionState.Success).items
                    } else {
                        emptyList()
                    }

                    // Deduplicate by id
                    val existingIds = existing.map { it.id }.toSet()
                    val newItems = newsPage.items.filter { it.id !in existingIds }
                    val allItems = existing + newItems

                    if (allItems.isEmpty()) {
                        _uiState.update { it.copy(news = SentimentNewsSectionState.Empty) }
                    } else {
                        _uiState.update {
                            it.copy(
                                news = SentimentNewsSectionState.Success(
                                    items = allItems,
                                    currentPage = newsPage.page,
                                    hasMore = newsPage.hasMore,
                                    isLoadingMore = false
                                )
                            )
                        }
                    }
                },
                onFailure = { e ->
                    // Only replace with Error on initial load. On loadMore, keep existing items.
                    val current = _uiState.value.news
                    if (current is SentimentNewsSectionState.Success) {
                        _uiState.update {
                            it.copy(
                                news = current.copy(isLoadingMore = false)
                            )
                        }
                    } else {
                        _uiState.update {
                            it.copy(
                                news = SentimentNewsSectionState.Error(
                                    e.message ?: "Unable to load news."
                                )
                            )
                        }
                    }
                }
            )
        }
    }

    fun loadMoreNews() {
        val currentNews = _uiState.value.news as? SentimentNewsSectionState.Success ?: return
        if (!currentNews.hasMore || currentNews.isLoadingMore) return
        if (currentSymbol.isNotEmpty()) {
            loadNews(currentSymbol, page = currentNews.currentPage + 1, reset = false)
        }
    }

    fun retryNews() {
        if (currentSymbol.isNotEmpty()) loadNews(currentSymbol, page = 1, reset = true)
    }
}
