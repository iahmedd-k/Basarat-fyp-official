package com.fyp.basarattradeinvest.domain.model.live

/**
 * A real-time price quote for a single PSX symbol, sourced from either the
 * WebSocket stream (quote_update / board_update) or the REST fallback
 * (/api/v1/market/quotes).
 *
 * All optional fields mirror the backend quote object as documented in the
 * GET /api/v1/ws/protocol endpoint. Never fabricate values — missing backend
 * fields are represented as null.
 */
data class LiveQuote(
    val symbol: String,
    /** Current / last-traded price */
    val current: Double?,
    /** Previous day's closing price */
    val ldcp: Double?,
    val open: Double?,
    val high: Double?,
    val low: Double?,
    val change: Double?,
    val changePct: Double?,
    val volume: Long?,
    /** ISO-8601 timestamp of the quote from the server */
    val asOf: String?,
    /** Staleness metadata supplied by the enclosing server response/event. */
    val isStale: Boolean = false,
    /** Source transport that delivered this quote */
    val source: LiveQuoteSource = LiveQuoteSource.WEBSOCKET
)

enum class LiveQuoteSource { WEBSOCKET, REST_FALLBACK }
