package com.fyp.basarattradeinvest.market

import com.fyp.basarattradeinvest.data.remote.api.LiveMarketApiService
import com.fyp.basarattradeinvest.data.remote.dto.live.LiveMarketStatusDto
import com.fyp.basarattradeinvest.data.remote.dto.live.RestQuotesResponseDto
import com.fyp.basarattradeinvest.data.remote.live.LiveMarketDataSource
import com.fyp.basarattradeinvest.domain.model.live.MarketSessionStatus
import com.google.gson.Gson
import com.google.gson.JsonObject
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response
import java.io.IOException

/**
 * The session body below is verbatim from GET /api/v1/market/live. Its `market_status` is
 * "market_hours", never "open" — the assumption that made the dashboard report "Market Closed"
 * during trading hours.
 */
class MarketSessionStatusTest {

    private companion object {
        const val LIVE_OPEN_JSON = """
        {
          "market_status": "market_hours",
          "is_market_open": true,
          "timezone": "Asia/Karachi",
          "current_time_pkt": "2026-10-05T11:15:21.964494+05:00",
          "as_of": "2026-10-05T06:15:15.483253+00:00",
          "is_stale": false,
          "quote_count": 747,
          "session_refresh_enabled": true,
          "transport": {
            "primary": "websocket",
            "fallback": "rest_polling",
            "websocket_path": "/api/v1/ws/market",
            "websocket_url": "ws://193.123.84.223:8000/api/v1/ws/market",
            "rest_quotes_path": "/api/v1/market/quotes",
            "protocol_docs_path": "/api/v1/ws/protocol",
            "recommended_rest_poll_seconds": 15,
            "session_refresh_seconds": 60,
            "protocol_version": "1.0"
          }
        }
        """
    }

    private fun dataSourceWith(response: Response<LiveMarketStatusDto>?, error: Exception? = null) =
        LiveMarketDataSource(
            okHttpClient = OkHttpClient(),
            liveMarketApiService = FakeLiveMarketApiService(response, error)
        )

    private fun success(json: String) =
        Response.success(Gson().fromJson(json, LiveMarketStatusDto::class.java))

    @Test
    fun `market_hours with is_market_open true reports an open market`() = runBlocking {
        assertEquals("market_status must not be the literal 'open'",
            "market_hours",
            Gson().fromJson(LIVE_OPEN_JSON, JsonObject::class.java).get("market_status").asString)

        val status = dataSourceWith(success(LIVE_OPEN_JSON)).getMarketSessionStatus().getOrThrow()

        assertTrue(status.isOpen)
        assertEquals("Market Open", status.label)
    }

    @Test
    fun `is_market_open false reports a closed market`() = runBlocking {
        val closed = LIVE_OPEN_JSON.replace("\"is_market_open\": true", "\"is_market_open\": false")

        val status = dataSourceWith(success(closed)).getMarketSessionStatus().getOrThrow()

        assertFalse(status.isOpen)
        assertEquals("Market Closed", status.label)
    }

    @Test
    fun `a body without is_market_open is unknown rather than closed`() = runBlocking {
        val noFlag = LIVE_OPEN_JSON.replace("\"is_market_open\": true,", "")

        val result = dataSourceWith(success(noFlag)).getMarketSessionStatus()

        assertTrue("missing is_market_open must not be reported as a session", result.isFailure)
    }

    @Test
    fun `an http error is a failure`() = runBlocking {
        val error = Response.error<LiveMarketStatusDto>(
            503,
            """{"detail":"Service unavailable"}""".toResponseBody("application/json".toMediaTypeOrNull())
        )

        val result = dataSourceWith(error).getMarketSessionStatus()

        assertTrue(result.isFailure)
        val message = result.exceptionOrNull()?.message.orEmpty()
        assertFalse(message.contains("Service unavailable"))
        assertTrue(message.contains("503"))
    }

    @Test
    fun `a transport failure is a failure`() = runBlocking {
        val result = dataSourceWith(response = null, error = IOException("timeout")).getMarketSessionStatus()

        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull() is IOException)
    }

    @Test
    fun `label covers both known sessions`() {
        assertEquals("Market Open", MarketSessionStatus(isOpen = true).label)
        assertEquals("Market Closed", MarketSessionStatus(isOpen = false).label)
    }

    private class FakeLiveMarketApiService(
        private val statusResponse: Response<LiveMarketStatusDto>?,
        private val statusError: Exception?
    ) : LiveMarketApiService {

        override suspend fun getLiveMarketStatus(): Response<LiveMarketStatusDto> =
            statusResponse ?: throw (statusError ?: IllegalStateException("No stubbed response"))

        override suspend fun getQuotes(
            path: String,
            symbols: String?,
            limit: Int,
            offset: Int
        ): Response<RestQuotesResponseDto> = throw NotImplementedError()
    }
}
