package com.fyp.basarattradeinvest.data.remote.live

import com.fyp.basarattradeinvest.data.remote.dto.live.WsServerMessageDto
import com.fyp.basarattradeinvest.data.remote.dto.live.WsQuoteDataDto
import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class LiveMarketProtocolDtoTest {

    @Test
    fun snapshotAndBoardUpdateDecodeSymbolKeyedData() {
        val frames = listOf(
            Triple(
                """{"event":"snapshot","data":{"OGDC":{"symbol":"OGDC","current":314.12,"change":-2.61,"change_pct":-0.82,"volume":769220}},"count":1,"as_of":"2026-10-01T09:17:02Z","is_stale":false}""",
                "snapshot",
                "2026-10-01T09:17:02Z"
            ),
            Triple(
                """{"event":"board_update","data":{"OGDC":{"symbol":"OGDC","current":314.12,"change":-2.61,"change_pct":-0.82,"volume":769220}},"count":1,"as_of":"2026-10-01T09:19:00Z","is_stale":false}""",
                "board_update",
                "2026-10-01T09:19:00Z"
            )
        )

        frames.forEach { (frame, expectedEvent, expectedAsOf) ->
            val message = Gson().fromJson(frame, WsServerMessageDto::class.java)
            val quote = Gson().fromJson(
                message.data?.get("OGDC"),
                WsQuoteDataDto::class.java
            )

            assertEquals(expectedEvent, message.event)
            assertEquals(expectedAsOf, message.asOf)
            assertEquals("OGDC", quote.symbol)
            assertEquals(314.12, quote.current!!, 0.0)
            assertEquals(-0.82, quote.changePct!!, 0.0)
            assertEquals(769220L, quote.volume)
            assertFalse(message.isStale!!)
        }
    }
}