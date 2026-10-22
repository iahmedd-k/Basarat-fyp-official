package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.live.LiveMarketDataSource
import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.MarketSessionStatus
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import com.fyp.basarattradeinvest.domain.repository.LiveMarketRepository
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Thin adapter that forwards calls from the domain layer to the
 * application-level [LiveMarketDataSource] singleton.
 *
 * Uses the singleton from [NetworkClient] by default so all ViewModels
 * share the same WebSocket connection.
 */
class LiveMarketRepositoryImpl(
    private val dataSource: LiveMarketDataSource = NetworkClient.liveMarketDataSource
) : LiveMarketRepository {

    override val connectionState: StateFlow<WsConnectionState>
        get() = dataSource.connectionState

    override val quoteUpdates: SharedFlow<LiveQuote>
        get() = dataSource.quoteUpdates

    override val quoteCache: StateFlow<Map<String, LiveQuote>>
        get() = dataSource.quoteCache

    override fun setSubscriptions(owner: String, symbols: Collection<String>) =
        dataSource.setSubscriptions(owner, symbols)

    override fun getCachedQuote(symbol: String): LiveQuote? = dataSource.getCachedQuote(symbol)

    override suspend fun getMarketSessionStatus(): Result<MarketSessionStatus> =
        dataSource.getMarketSessionStatus()
}
