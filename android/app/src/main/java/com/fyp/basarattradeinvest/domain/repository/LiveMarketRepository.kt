package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.MarketSessionStatus
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Domain-layer contract for the live market data layer.
 *
 * ViewModels depend on this interface, not on [LiveMarketDataSource] directly,
 * keeping the architecture clean and testable.
 */
interface LiveMarketRepository {

    /** Current WebSocket connection state. */
    val connectionState: StateFlow<WsConnectionState>

    /**
     * Hot stream of individual quote ticks.
     * Emits every time a new quote arrives via WebSocket or REST fallback.
     */
    val quoteUpdates: SharedFlow<LiveQuote>

    /** Snapshot cache: symbol → latest received quote. */
    val quoteCache: StateFlow<Map<String, LiveQuote>>

    /** Replace one screen's requested symbols while preserving other screens' subscriptions. */
    fun setSubscriptions(owner: String, symbols: Collection<String>)

    /** Retrieve the latest cached quote for a symbol (null if not yet received). */
    fun getCachedQuote(symbol: String): LiveQuote?

    /**
     * Current PSX trading session. A failure means the session is unknown and the
     * caller must not present it as closed.
     */
    suspend fun getMarketSessionStatus(): Result<MarketSessionStatus>
}
