package com.fyp.basarattradeinvest.feature.dashboard

import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Property 13: UiState Default Compatibility
 * Verifies HomeUiState.Success can be constructed without live fields
 * and that defaults are backward-compatible.
 *
 * Validates: Requirements 1.3
 */
class HomeUiStateTest {

    @Test
    fun `Success default liveQuotes is emptyMap`() {
        val state = HomeUiState.Success(userName = "TestUser")
        assertTrue("liveQuotes should default to emptyMap", state.liveQuotes.isEmpty())
    }

    @Test
    fun `Success default wsConnectionState is Idle`() {
        val state = HomeUiState.Success(userName = "TestUser")
        assertEquals(
            "wsConnectionState should default to Idle",
            WsConnectionState.Idle,
            state.wsConnectionState
        )
    }

    @Test
    fun `Success copy updates liveQuotes`() {
        val initial = HomeUiState.Success(userName = "TestUser")
        val quote = com.fyp.basarattradeinvest.domain.model.live.LiveQuote(
            symbol = "OGDC",
            current = 245.10,
            ldcp = null, open = null, high = null, low = null,
            change = null, changePct = null, volume = null, asOf = null
        )
        val updated = initial.copy(liveQuotes = mapOf("OGDC" to quote))
        assertEquals(1, updated.liveQuotes.size)
        assertEquals("OGDC", updated.liveQuotes["OGDC"]?.symbol)
    }
}
