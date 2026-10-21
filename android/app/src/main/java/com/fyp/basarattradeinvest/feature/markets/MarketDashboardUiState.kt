package com.fyp.basarattradeinvest.feature.markets

import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.model.market.SectorPerformance
import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.MarketSessionStatus
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState

/**
 * One chip drives one table. The index chips load that index's constituents and the mover chips
 * load the filtered symbol lists, so both feed the same rows.
 */
enum class MarketListSelection(val chipLabel: String, val headerTitle: String) {
    KSE_100("KSE-100", "KSE-100 Constituents \u203A"),
    KSE_30("KSE-30", "KSE-30 Constituents \u203A"),
    KMI_30("KMI-30", "KMI-30 Constituents \u203A"),
    GAINERS("Gainers", "Top Gainers \u203A"),
    LOSERS("Losers", "Top Losers \u203A"),
    VOLUME_SPIKES("Volume Spikes", "Volume Spikes \u203A"),
    MOST_ACTIVE("Most Active", "Most Active \u203A");

    val isIndex: Boolean get() = this == KSE_100 || this == KSE_30 || this == KMI_30
}

sealed interface MarketDashboardUiState {
    data object Loading : MarketDashboardUiState

    data class Success(
        val indices: List<MarketIndex>,
        val rows: List<MarketStock>,
        val selection: MarketListSelection,
        val isRowsLoading: Boolean = false,
        val sectors: List<SectorPerformance>,
        val lastUpdated: String,
        val liveQuotes: Map<String, LiveQuote> = emptyMap(),
        val wsConnectionState: WsConnectionState = WsConnectionState.Idle,
        /** Null when the backend did not report a session; the header hides instead of guessing. */
        val marketSession: MarketSessionStatus? = null
    ) : MarketDashboardUiState

    data object Empty : MarketDashboardUiState

    data class Error(val message: String) : MarketDashboardUiState
}
