package com.fyp.basarattradeinvest.dashboard

import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.feature.dashboard.HomeUiState
import com.fyp.basarattradeinvest.feature.dashboard.WatchlistUiState
import com.fyp.basarattradeinvest.domain.model.watchlist.Watchlist
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@ExperimentalCoroutinesApi
class HomeViewModelUnitTest {

    @Before
    fun setUp() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testHomeUiStateSuccessProperties() {
        val watchlist = Watchlist(
            id = "watchlist-1",
            name = "Default",
            items = listOf(
                WatchlistItem(
                    id = "item-1",
                    watchlistId = "watchlist-1",
                    symbol = "ENGRO",
                    name = "Engro Corp",
                    currentPrice = 312.40,
                    change = 7.35,
                    changePercent = 2.41,
                    isStale = false
                )
            )
        )
        val indices = listOf(
            MarketIndex("1", "KSE-100", "KSE100", 170498.94, -1733.57, -1.01, 172491.16, 170418.38),
            MarketIndex("2", "KSE-30", "KSE30", 50739.69, -544.11, -1.06, 51366.74, 50697.28)
        )
        val news = listOf(
            NewsArticle("n1", "SYS", false, "Dawn News", "2026-09-26T12:00:00Z", 0.75, "Bullish", "Tech stocks rally", "Overview snippet")
        )

        val state = HomeUiState.Success(
            userName = "Abdul Rehman",
            marketStatus = "Market Open",
            isMarketOpen = true,
            marketIndices = indices,
            selectedBenchmarkIndex = indices[0],
            selectedTimeframe = "1D",
            watchlist = WatchlistUiState.Success(watchlist),
            recentNews = news,
            activeAlertsCount = 2
        )

        // 1. Verify basic properties
        assertEquals("Abdul Rehman", state.userName)
        assertEquals("Market Open", state.marketStatus)
        assertTrue(state.isMarketOpen)
        assertEquals(2, state.marketIndices.size)
        assertEquals(1, (state.watchlist as WatchlistUiState.Success).watchlist.items.size)
        assertEquals(2, state.activeAlertsCount)

        // 2. Verify breadth stays hidden rather than guessed until the endpoint answers
        assertNull(state.sentiment)

        val sentiment = MarketSentiment(
            overallScore = 61,
            sentimentLabel = "Bullish",
            positivePercent = 45,
            neutralPercent = 15,
            negativePercent = 40,
            advanceDeclineRatio = 1.42,
            advancing = 195,
            declining = 137,
            unchanged = 68
        )
        val withSentiment = state.copy(sentiment = sentiment)
        assertEquals(195, withSentiment.sentiment?.advancing)
        assertEquals(1.42, withSentiment.sentiment?.advanceDeclineRatio ?: 0.0, 0.0)

        // 3. Verify backward compatibility defaults
        assertEquals("04182-PSX", state.subAccount)
        assertTrue(state.isCdcActive)
        assertEquals("1M", state.selectedPeriod)
        assertNull(state.portfolioOverview)
        assertNull(state.allocation)
        assertTrue(state.topHoldings.isEmpty())
        assertNull(state.riskSummary)
    }

    @Test
    fun testHomeViewModelStartsInLoadingState() {
        val viewModel = com.fyp.basarattradeinvest.feature.dashboard.HomeViewModel(autoLoad = false)
        assertTrue(viewModel.uiState.value is HomeUiState.Loading)
    }

    @Test
    fun testHomeUiStateErrorAndLoading() {
        val loading: HomeUiState = HomeUiState.Loading
        assertNotNull(loading)

        val error: HomeUiState = HomeUiState.Error("Network error loading PSX market data")
        assertEquals("Network error loading PSX market data", (error as HomeUiState.Error).message)
    }
}
