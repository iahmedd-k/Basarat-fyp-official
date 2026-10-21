package com.fyp.basarattradeinvest.data.remote.live

import android.util.Log
import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.remote.api.LiveMarketApiService
import com.fyp.basarattradeinvest.data.remote.dto.live.RestQuotesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.live.WsClientMessageDto
import com.fyp.basarattradeinvest.data.remote.dto.live.WsQuoteDataDto
import com.fyp.basarattradeinvest.data.remote.dto.live.WsServerMessageDto
import com.fyp.basarattradeinvest.domain.model.live.LiveQuote
import com.fyp.basarattradeinvest.domain.model.live.LiveQuoteSource
import com.fyp.basarattradeinvest.domain.model.live.MarketSessionStatus
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState
import com.google.gson.Gson
import com.google.gson.JsonSyntaxException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.concurrent.atomic.AtomicInteger

/**
 * Application-level singleton that owns the single shared OkHttp WebSocket
 * connection discovered from the backend's live-market endpoint.
 *
 * Architecture:
 *  - Single [WebSocket] shared across Home, Markets, and Stock Detail.
 *  - Callers subscribe/unsubscribe per-symbol. When the last subscriber is
 *    removed the socket stays open (backend is cheap); it only closes if the
 *    app is backgrounded for longer than [IDLE_CLOSE_DELAY_MS].
 *  - On failure the source falls back to REST polling of /api/v1/market/quotes
 *    every [restPollIntervalMs] and schedules a WebSocket reconnect with
 *    exponential backoff (1 s → 2 → 4 → 8 → 16 → 30 s cap).
 *
 * Threading: all state mutations go through [scope] (IO dispatcher). Callers
 * collect flows on their own lifecycle scope.
 */
class LiveMarketDataSource(
    private val okHttpClient: OkHttpClient,
    private val liveMarketApiService: LiveMarketApiService
) {
    companion object {
        private const val TAG = "LiveMarketDataSource"
        private const val IDLE_CLOSE_DELAY_MS = 60_000L
        private const val MAX_BACKOFF_MS = 30_000L
        private const val BASE_BACKOFF_MS = 1_000L
    }

    // ------------------------------------------------------------------
    // Public state
    // ------------------------------------------------------------------

    private val _connectionState =
        MutableStateFlow<WsConnectionState>(WsConnectionState.Idle)
    val connectionState: StateFlow<WsConnectionState> = _connectionState.asStateFlow()

    /** Hot stream of individual quote ticks (symbol-keyed). */
    private val _quoteUpdates = MutableSharedFlow<LiveQuote>(extraBufferCapacity = 64)
    val quoteUpdates: SharedFlow<LiveQuote> = _quoteUpdates.asSharedFlow()

    /** Snapshot cache: symbol → latest quote. */
    private val _quoteCache = MutableStateFlow<Map<String, LiveQuote>>(emptyMap())
    val quoteCache: StateFlow<Map<String, LiveQuote>> = _quoteCache.asStateFlow()

    // ------------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------------

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val gson = Gson()
    private val mutex = Mutex()
    private val connectionMutex = Mutex()
    private val subscriptions = mutableSetOf<String>() // currently subscribed symbols
    private val subscriptionsByOwner = mutableMapOf<String, Set<String>>()
    @Volatile private var webSocket: WebSocket? = null
    @Volatile private var websocketUrl: String? = null
    private var restQuotesPath = "/api/v1/market/quotes"
    private var restTransportDiscovered = false
    private val reconnectAttempt = AtomicInteger(0)
    private var reconnectJob: Job? = null
    private var restPollJob: Job? = null
    private var idleCloseJob: Job? = null
    @Volatile private var restPollIntervalMs = 15_000L
    @Volatile private var isConnected = false
    @Volatile private var isShuttingDown = false

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    /** Replace this owner's symbol set without affecting other screen owners. */
    fun setSubscriptions(owner: String, symbols: Collection<String>) {
        if (owner.isBlank()) return
        scope.launch {
            val normalized = symbols.map { it.trim().uppercase() }.filter { it.isNotEmpty() }.distinct()
            val (added, removed) = mutex.withLock {
                val oldUnion = subscriptions.toSet()
                if (normalized.isEmpty()) subscriptionsByOwner.remove(owner)
                else subscriptionsByOwner[owner] = normalized.toSet()
                val newUnion = subscriptionsByOwner.values.flatten().toSet()
                subscriptions.clear()
                subscriptions.addAll(newUnion)
                (newUnion - oldUnion) to (oldUnion - newUnion)
            }
            if (removed.isNotEmpty() && isConnected) {
                val payload = WsClientMessageDto(action = "unsubscribe", symbols = removed.toList())
                webSocket?.send(gson.toJson(payload))
            }
            if (normalized.isNotEmpty()) {
                cancelIdleClose()
                ensureConnected()
                if (isConnected && added.isNotEmpty()) sendSubscribe(added.toList())
            } else if (mutex.withLock { subscriptions.isEmpty() }) {
                scheduleIdleClose()
            }
        }
    }

    /**
     * Retrieve the latest cached quote for a symbol (null if not yet received).
     */
    fun getCachedQuote(symbol: String): LiveQuote? =
        _quoteCache.value[symbol.uppercase()]

    /**
     * Real trading-session state from the discovery endpoint. Fails rather than
     * guessing when the backend does not report `is_market_open`, so callers can
     * hide the indicator instead of asserting a session they never observed.
     */
    suspend fun getMarketSessionStatus(): Result<MarketSessionStatus> {
        return try {
            val response = liveMarketApiService.getLiveMarketStatus()
            if (!response.isSuccessful) {
                return Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
            val body = response.body()
            val isOpen = body?.isMarketOpen
                ?: return Result.failure(Exception("Market session status unavailable"))
            Result.success(MarketSessionStatus(isOpen = isOpen))
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(error)
        }
    }

    /**
     * Release all resources. Call from Application.onTerminate or test teardown.
     */
    fun shutdown() {
        isShuttingDown = true
        reconnectJob?.cancel()
        restPollJob?.cancel()
        idleCloseJob?.cancel()
        webSocket?.close(1000, "App shutdown")
        webSocket = null
        scope.cancel()
    }

    // ------------------------------------------------------------------
    // Connection management
    // ------------------------------------------------------------------

    private suspend fun ensureConnected() {
        connectionMutex.withLock {
            if (isConnected || _connectionState.value is WsConnectionState.Connecting || reconnectJob?.isActive == true) return
            reconnectJob?.cancel()
            _connectionState.value = WsConnectionState.Connecting(reconnectAttempt.get().coerceAtLeast(1))
            if (!restTransportDiscovered && !discoverTransport()) {
                onDisconnected("Unable to discover live market transport")
                return
            }
            openWebSocket(attempt = reconnectAttempt.get())
        }
    }

    private suspend fun discoverTransport(): Boolean {
        return try {
            val response = liveMarketApiService.getLiveMarketStatus()
            val transport = response.takeIf { it.isSuccessful }?.body()?.transport
            val discoveredUrl = transport?.websocketUrl?.takeIf { it.isNotBlank() } ?: return false
            websocketUrl = discoveredUrl
            transport.restQuotesPath?.takeIf { it.isNotBlank() }?.let { restQuotesPath = it }
            transport.recommendedRestPollSeconds
                ?.takeIf { it > 0 }
                ?.let { restPollIntervalMs = it * 1_000L }
            restTransportDiscovered = true
            true
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Log.w(TAG, "Live market discovery failed: ${error.message}")
            false
        }
    }

    private fun openWebSocket(attempt: Int) {
        val url = websocketUrl ?: run {
            onDisconnected("Live market WebSocket URL is unavailable")
            return
        }
        val state = if (attempt == 0) WsConnectionState.Connecting(1)
        else WsConnectionState.Reconnecting(attempt)
        _connectionState.value = state

        val request = Request.Builder().url(url).build()
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {

            override fun onOpen(ws: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket opened (attempt=$attempt)")
                isConnected = true
                reconnectAttempt.set(0)
                _connectionState.value = WsConnectionState.Live
                stopRestFallback()
                // Re-subscribe all tracked symbols after (re)connect
                scope.launch {
                    val subs = mutex.withLock { subscriptions.toList() }
                    if (subs.isNotEmpty()) sendSubscribe(subs)
                }
            }

            override fun onMessage(ws: WebSocket, text: String) {
                scope.launch { handleServerMessage(text) }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "WebSocket failure: ${t.message}")
                onDisconnected(reason = t.message)
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $code $reason")
                scope.launch {
                    val hasSubscribers = mutex.withLock { subscriptions.isNotEmpty() }
                    if (!isShuttingDown && hasSubscribers) {
                        onDisconnected(reason = reason)
                    } else {
                        isConnected = false
                        _connectionState.value = WsConnectionState.Closed
                    }
                }
            }
        })
    }

    private fun onDisconnected(reason: String?) {
        isConnected = false
        val attempt = reconnectAttempt.incrementAndGet()
        val backoffMs = calculateBackoff(attempt)
        val backoffSeconds = (backoffMs / 1000).toInt()
        _connectionState.value = WsConnectionState.Delayed(backoffSeconds)
        Log.d(TAG, "Scheduling reconnect in ${backoffMs}ms (attempt $attempt)")

        startRestFallback()

        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            var remaining = backoffSeconds
            while (remaining > 0 && isActive) {
                _connectionState.value = WsConnectionState.Delayed(remaining)
                delay(1_000L)
                remaining--
            }
            if (isActive && subscriptions.isNotEmpty()) {
                if (!restTransportDiscovered && !discoverTransport()) {
                    onDisconnected("Unable to rediscover live market transport")
                } else {
                    openWebSocket(attempt)
                }
            }
        }
    }

    private fun calculateBackoff(attempt: Int): Long {
        val exp = minOf(attempt - 1, 5)
        return minOf(BASE_BACKOFF_MS * (1L shl exp), MAX_BACKOFF_MS)
    }

    // ------------------------------------------------------------------
    // REST fallback polling
    // ------------------------------------------------------------------

    private fun startRestFallback() {
        if (restPollJob?.isActive == true) return
        restPollJob = scope.launch {
            while (isActive && !isConnected) {
                pollRestQuotes()
                delay(restPollIntervalMs)
            }
        }
    }

    private fun stopRestFallback() {
        restPollJob?.cancel()
        restPollJob = null
    }

    private suspend fun pollRestQuotes() {
        val subs = mutex.withLock { subscriptions.toSet() }
        if (subs.isEmpty()) return
        try {
            val response = liveMarketApiService.getQuotes(
                path = restQuotesPath,
                symbols = subs.joinToString(",")
            )
            if (response.isSuccessful) {
                val body = response.body() ?: return
                body.recommendedPollSeconds?.let { restPollIntervalMs = it * 1000L }
                val stocks = body.stocks ?: return
                processQuoteList(
                    stocks,
                    source = LiveQuoteSource.REST_FALLBACK,
                    asOf = body.asOf,
                    isStale = body.isStale
                )
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            Log.w(TAG, "REST fallback poll failed: ${e.message}")
        }
    }

    // ------------------------------------------------------------------
    // Message parsing
    // ------------------------------------------------------------------

    private fun handleServerMessage(text: String) {
        try {
            val msg = gson.fromJson(text, WsServerMessageDto::class.java) ?: return
            when (msg.event) {
                "board_update", "snapshot" -> processQuoteMap(msg)
                "quote_update" -> Log.w(TAG, "Ignoring quote_update with undocumented payload shape")
                "connected" -> Log.d(TAG, "Server: connected event")
                "subscribed" -> Log.d(TAG, "Server: subscribed event")
                "unsubscribed" -> Log.d(TAG, "Server: unsubscribed event")
                "subscriptions" -> Log.d(TAG, "Server: subscription list received")
                "pong" -> Log.v(TAG, "Server: pong")
                "error" -> Log.w(TAG, "Server reported a WebSocket error")
                else -> Log.v(TAG, "Unhandled WS event: ${msg.event}")
            }
        } catch (e: JsonSyntaxException) {
            Log.w(TAG, "Failed to parse WS message: ${e.message}")
        }
    }

    private fun processQuoteMap(message: WsServerMessageDto) {
        val data = message.data ?: return
        val quotes = data.entrySet().mapNotNull { (symbol, value) ->
            runCatching { gson.fromJson(value, WsQuoteDataDto::class.java) }
                .getOrNull()
                ?.let { if (it.symbol.isNullOrBlank()) it.copy(symbol = symbol) else it }
        }
        processQuoteList(
            quotes,
            source = LiveQuoteSource.WEBSOCKET,
            asOf = message.asOf,
            isStale = message.isStale
        )
    }

    private fun processQuoteList(
        list: List<WsQuoteDataDto>,
        source: LiveQuoteSource,
        asOf: String? = null,
        isStale: Boolean? = null
    ) {
        if (list.isEmpty()) return
        val updates = mutableMapOf<String, LiveQuote>()
        list.forEach { dto ->
            val sym = dto.symbol?.uppercase() ?: return@forEach
            updates[sym] = dto.toQuote(source, asOf, isStale)
        }
        scope.launch {
            _quoteCache.update { current -> current + updates }
            updates.values.forEach { _quoteUpdates.emit(it) }
        }
    }

    // ------------------------------------------------------------------
    // Send helpers
    // ------------------------------------------------------------------

    private fun sendSubscribe(symbols: List<String>) {
        if (!isConnected || symbols.isEmpty()) return
        val msg = WsClientMessageDto(action = "subscribe", symbols = symbols)
        webSocket?.send(gson.toJson(msg))
        Log.d(TAG, "Subscribed: $symbols")
    }

    // ------------------------------------------------------------------
    // Idle-close management
    // ------------------------------------------------------------------

    private fun scheduleIdleClose() {
        idleCloseJob?.cancel()
        idleCloseJob = scope.launch {
            delay(IDLE_CLOSE_DELAY_MS)
            if (subscriptions.isEmpty()) {
                Log.d(TAG, "No subscribers — closing idle WebSocket")
                webSocket?.close(1000, "idle")
                webSocket = null
                isConnected = false
                reconnectJob?.cancel()
                stopRestFallback()
                _connectionState.value = WsConnectionState.Closed
            }
        }
    }

    private fun cancelIdleClose() {
        idleCloseJob?.cancel()
        idleCloseJob = null
    }
}

// ------------------------------------------------------------------
// DTO → domain extension
// ------------------------------------------------------------------

private fun WsQuoteDataDto.toQuote(
    source: LiveQuoteSource,
    responseAsOf: String? = null,
    responseIsStale: Boolean? = null
): LiveQuote = LiveQuote(
    symbol = symbol?.uppercase() ?: "",
    current = current,
    ldcp = ldcp,
    open = open,
    high = high,
    low = low,
    change = change,
    changePct = changePct,
    volume = volume,
    asOf = asOf ?: responseAsOf,
    isStale = responseIsStale ?: false,
    source = source
)
