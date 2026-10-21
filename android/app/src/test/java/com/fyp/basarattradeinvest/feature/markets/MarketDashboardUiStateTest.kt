package com.fyp.basarattradeinvest.feature.markets

import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Property 13: UiState Default Compatibility for MarketDashboardUiState.
 *
 * Validates: Requirements 4.3
 */
class MarketDashboardUiStateTest {

    private fun makeSuccess() = MarketDashboardUiState.Success(
        indices = emptyList(),
        rows = emptyList(),
        selection = MarketListSelection.GAINERS,
        sectors = emptyList(),
        lastUpdated = "12:00"
    )

    @Test
    fun `Success default liveQuotes is emptyMap`() {
        val state = makeSuccess()
        assertTrue("liveQuotes should default to emptyMap", state.liveQuotes.isEmpty())
    }

    @Test
    fun `Success default wsConnectionState is Idle`() {
        val state = makeSuccess()
        assertEquals(
            "wsConnectionState should default to Idle",
            WsConnectionState.Idle,
            state.wsConnectionState
        )
    }
}
