package com.fyp.basarattradeinvest.domain.model.live

/**
 * Lifecycle states of the shared WebSocket connection.
 *
 * Fragments observe this via the LiveMarketRepository and display a
 * non-intrusive chip/badge in their app bars.
 */
sealed interface WsConnectionState {
    /** No connection attempt started yet. */
    data object Idle : WsConnectionState

    /** Attempting initial connection or a reconnect attempt. */
    data class Connecting(val attempt: Int = 1) : WsConnectionState

    /** WebSocket handshake succeeded; real-time data is flowing. */
    data object Live : WsConnectionState

    /**
     * WebSocket failed; the data layer is falling back to REST polling.
     * [nextRetryInSeconds] is the countdown before the next WS reconnect.
     */
    data class Delayed(val nextRetryInSeconds: Int = 0) : WsConnectionState

    /** A reconnect attempt is in progress (shown after first failure). */
    data class Reconnecting(val attempt: Int) : WsConnectionState

    /** The connection was closed intentionally (e.g. app background / no subscribers). */
    data object Closed : WsConnectionState
}
