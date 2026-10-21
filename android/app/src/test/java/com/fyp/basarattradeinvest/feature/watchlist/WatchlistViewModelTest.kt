package com.fyp.basarattradeinvest.feature.watchlist

import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.MarketSessionStatus
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import com.fyp.basarattradeinvest.domain.model.watchlist.Watchlist
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistItem
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistMembership
import com.fyp.basarattradeinvest.domain.repository.LiveMarketRepository
import com.fyp.basarattradeinvest.domain.repository.WatchlistRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class WatchlistViewModelTest {

    @Before
    fun setUp() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private class FakeWatchlistRepository : WatchlistRepository {
        val updates = MutableSharedFlow<Watchlist>(extraBufferCapacity = 1)
        override val watchlistUpdates: SharedFlow<Watchlist> = updates

        var nextResult: Result<Watchlist> = Result.success(
            Watchlist(id = "wl-1", name = "Default", items = listOf(watchlistItem("ENGRO", 402.10), watchlistItem("HUBCO", 118.55)))
        )
        val removalRequests = mutableListOf<Pair<String, List<String>>>()
        var removeResult: Result<Unit> = Result.success(Unit)

        override suspend fun getDefaultWatchlist(): Result<Watchlist> = nextResult

        override suspend fun checkSymbol(symbol: String): Result<WatchlistMembership> =
            Result.success(WatchlistMembership(symbol, isInWatchlist = true, watchlistIds = listOf("wl-1")))

        override suspend fun addToDefaultWatchlist(symbol: String): Result<Watchlist> = nextResult

        override suspend fun removeFromWatchlists(
            symbol: String,
            watchlistIds: List<String>
        ): Result<Unit> {
            removalRequests += symbol to watchlistIds
            if (removeResult.isSuccess) {
                val remaining = nextResult.getOrNull()?.items.orEmpty().filterNot { it.symbol == symbol }
                nextResult = Result.success(Watchlist("wl-1", "Default", remaining))
                updates.emit(Watchlist("wl-1", "Default", remaining))
            }
            return removeResult
        }
    }

    private class FakeLiveMarketRepository : LiveMarketRepository {
        override val connectionState: StateFlow<WsConnectionState> = MutableStateFlow(WsConnectionState.Idle)
        override val quoteUpdates: SharedFlow<LiveQuote> = MutableSharedFlow()
        override val quoteCache: StateFlow<Map<String, LiveQuote>> = MutableStateFlow(emptyMap())
        var subscribedSymbols: Collection<String> = emptyList()
        override fun setSubscriptions(owner: String, symbols: Collection<String>) {
            subscribedSymbols = symbols
        }

        override fun getCachedQuote(symbol: String): LiveQuote? = null
        override suspend fun getMarketSessionStatus(): Result<MarketSessionStatus> =
            Result.failure(UnsupportedOperationException())
    }

    @Test
    fun testLoad_publishesRepositoryItems() = runBlocking {
        val repo = FakeWatchlistRepository()
        val vm = WatchlistViewModel(repo, FakeLiveMarketRepository())

        val state = vm.uiState.value as WatchlistScreenUiState.Loaded
        assertEquals(listOf("ENGRO", "HUBCO"), state.items.map { it.symbol })
        assertEquals(402.10, state.items.first().currentPrice ?: 0.0, 0.001)
        assertTrue(state.pendingRemovals.isEmpty())
    }

    @Test
    fun testLoad_failureWithoutData_showsError() = runBlocking {
        val repo = FakeWatchlistRepository()
        repo.nextResult = Result.failure(IllegalStateException("Sign in to view and manage your watchlist."))

        val vm = WatchlistViewModel(repo, FakeLiveMarketRepository())

        val state = vm.uiState.value as WatchlistScreenUiState.Error
        assertEquals("Sign in to view and manage your watchlist.", state.message)
    }

    @Test
    fun testRemove_usesTheItemsOwnWatchlistIdAndDropsTheRow() = runBlocking {
        val repo = FakeWatchlistRepository()
        val vm = WatchlistViewModel(repo, FakeLiveMarketRepository())

        vm.remove("ENGRO", "wl-1")

        // The repository deletes on the server and publishes the shrunken watchlist, so the
        // row is gone and nothing is left marked in flight.
        val settled = vm.uiState.value as WatchlistScreenUiState.Loaded
        assertEquals(listOf("HUBCO"), settled.items.map { it.symbol })
        assertTrue(settled.pendingRemovals.isEmpty())
        assertEquals(listOf("ENGRO" to listOf("wl-1")), repo.removalRequests)
    }

    @Test
    fun testRemove_failure_keepsTheRowAndClearsPending() = runBlocking {
        val repo = FakeWatchlistRepository()
        repo.removeResult = Result.failure(IllegalStateException("Network unavailable"))
        val vm = WatchlistViewModel(repo, FakeLiveMarketRepository())

        vm.remove("ENGRO", "wl-1")

        val state = vm.uiState.value as WatchlistScreenUiState.Loaded
        assertTrue(state.pendingRemovals.isEmpty())
        assertEquals(listOf("ENGRO", "HUBCO"), state.items.map { it.symbol })
    }

    @Test
    fun testLiveUpdates_subscribeOnlyTheWatchlistSymbols() = runBlocking {
        val live = FakeLiveMarketRepository()
        val vm = WatchlistViewModel(FakeWatchlistRepository(), live)

        vm.setLiveUpdatesActive(true)
        assertEquals(listOf("ENGRO", "HUBCO"), live.subscribedSymbols.toList())

        vm.setLiveUpdatesActive(false)
        assertTrue(live.subscribedSymbols.isEmpty())
    }
}

private fun watchlistItem(symbol: String, price: Double?) = WatchlistItem(
    id = "item-$symbol",
    watchlistId = "wl-1",
    symbol = symbol,
    name = "$symbol Holdings",
    currentPrice = price,
    change = null,
    changePercent = 1.25,
    isStale = false
)
