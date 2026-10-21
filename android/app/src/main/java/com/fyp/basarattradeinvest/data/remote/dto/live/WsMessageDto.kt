package com.fyp.basarattradeinvest.data.remote.dto.live

import com.google.gson.annotations.SerializedName
import com.google.gson.JsonObject

// ---------------------------------------------------------------------------
// Outbound client → server frames
// Source of truth: GET /api/v1/ws/protocol
// client_actions: subscribe, unsubscribe, get_snapshot, get_subscriptions, ping
// ---------------------------------------------------------------------------

data class WsClientMessageDto(
    @SerializedName("action") val action: String,
    @SerializedName("symbols") val symbols: List<String>? = null
)

// ---------------------------------------------------------------------------
// Inbound server → client frames
// server_events: connected, subscribed, unsubscribed, snapshot, board_update,
//                quote_update, pong, error, authenticated, unauthenticated
// ---------------------------------------------------------------------------

/**
 * Base wrapper for every server frame.
 * Only [event] is guaranteed to be present; specific sub-payloads are parsed
 * conditionally in [LiveMarketDataSource].
 */
data class WsServerMessageDto(
    @SerializedName("event") val event: String?,
    @SerializedName("data") val data: JsonObject?,
    @SerializedName("symbols") val symbols: List<String>?,
    @SerializedName("as_of") val asOf: String?,
    @SerializedName("is_stale") val isStale: Boolean?,
    @SerializedName("timestamp") val timestamp: String?
)

/**
 * Shared quote object used inside board_update, quote_update, and snapshot events.
 * Field names verified against the backend /api/v1/market/quotes response, which
 * mirrors the WS payload shape.
 */
data class WsQuoteDataDto(
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("current") val current: Double?,
    @SerializedName("ldcp") val ldcp: Double?,
    @SerializedName("open") val open: Double?,
    @SerializedName("high") val high: Double?,
    @SerializedName("low") val low: Double?,
    @SerializedName("change") val change: Double?,
    @SerializedName("change_pct") val changePct: Double?,
    @SerializedName("volume") val volume: Long?,
    @SerializedName("as_of") val asOf: String?,
    @SerializedName("name") val name: String?,
    @SerializedName("sector") val sector: String?,
    @SerializedName("market_cap_m") val marketCapM: Double?
)

// ---------------------------------------------------------------------------
// REST fallback  GET /api/v1/market/quotes
// Verified response structure: {stocks, total, limit, offset, filtered,
//                               as_of, is_stale, recommended_poll_seconds,
//                               transport_hint}
// ---------------------------------------------------------------------------

data class RestQuotesResponseDto(
    @SerializedName("stocks") val stocks: List<WsQuoteDataDto>?,
    @SerializedName("total") val total: Int?,
    @SerializedName("as_of") val asOf: String?,
    @SerializedName("is_stale") val isStale: Boolean?,
    @SerializedName("recommended_poll_seconds") val recommendedPollSeconds: Int?
)

// REST  GET /api/v1/market/live  (discovery / bootstrap)
data class LiveMarketStatusDto(
    @SerializedName("market_status") val marketStatus: String?,
    @SerializedName("is_market_open") val isMarketOpen: Boolean?,
    @SerializedName("is_stale") val isStale: Boolean?,
    @SerializedName("quote_count") val quoteCount: Int?,
    @SerializedName("as_of") val asOf: String?,
    @SerializedName("transport") val transport: LiveTransportDto?
)

data class LiveTransportDto(
    @SerializedName("websocket_url") val websocketUrl: String?,
    @SerializedName("rest_quotes_path") val restQuotesPath: String?,
    @SerializedName("recommended_rest_poll_seconds") val recommendedRestPollSeconds: Int?
)
