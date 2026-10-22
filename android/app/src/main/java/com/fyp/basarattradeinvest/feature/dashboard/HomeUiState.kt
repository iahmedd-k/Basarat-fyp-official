package com.fyp.basarattradeinvest.feature.dashboard

import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem
import com.fyp.basarattradeinvest.domain.model.market.BenchmarkTrend
import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import com.fyp.basarattradeinvest.domain.model.portfolio.PerformancePoint
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.domain.model.watchlist.Watchlist

sealed interface HomeUiState {
    data object Loading : HomeUiState

    data class Success(
        val userName: String,
        // Null until the backend answers for this load; the header pill hides rather
        // than claiming the market is closed.
        val marketStatus: String? = null,
        val isMarketOpen: Boolean = false,
        val marketIndices: List<MarketIndex> = emptyList(),
        val selectedBenchmarkIndex: MarketIndex? = null,
        val selectedTimeframe: String = "1D",
        // Derived from constituent price history in a second pass, so it lands after the
        // benchmark's headline numbers.
        val benchmarkTrend: BenchmarkTrendUiState = BenchmarkTrendUiState.Empty,
        val watchlist: WatchlistUiState = WatchlistUiState.Loading,
        // Null until /market/sentiment-overview answers; both moved cards hide rather
        // than painting placeholder breadth or sentiment figures.
        val sentiment: MarketSentiment? = null,
        val recentNews: List<NewsArticle> = emptyList(),
        val activeAlertsCount: Int = 0,
        val unresolvedAlerts: List<AlertItem> = emptyList(),
        // Optional compatibility fields with defaults
        val subAccount: String = "04182-PSX",
        val isCdcActive: Boolean = true,
        val portfolioOverview: PortfolioOverview? = null,
        val performancePoints: List<PerformancePoint> = emptyList(),
        val selectedPeriod: String = "1M",
        val allocation: PortfolioAllocation? = null,
        val topHoldings: List<HoldingItem> = emptyList(),
        val riskSummary: PortfolioVaR? = null,
        val liveQuotes: Map<String, LiveQuote> = emptyMap(),
        val wsConnectionState: WsConnectionState = WsConnectionState.Idle
    ) : HomeUiState

    data class Error(val message: String) : HomeUiState
}

sealed interface WatchlistUiState {
    data object Loading : WatchlistUiState
    data class Success(val watchlist: Watchlist) : WatchlistUiState
    data object Empty : WatchlistUiState
    data class Error(val message: String) : WatchlistUiState
}

/**
 * [Loading] means a build for the selected pill is in flight, so the line already on screen stays
 * there instead of leaving a hole in a card the rest of which has finished loading. [Empty] means
 * this pill has nothing to plot, and a pill with no data must not borrow another pill's line.
 */
sealed interface BenchmarkTrendUiState {
    data object Loading : BenchmarkTrendUiState
    data class Success(val trend: BenchmarkTrend) : BenchmarkTrendUiState
    data object Empty : BenchmarkTrendUiState
}
