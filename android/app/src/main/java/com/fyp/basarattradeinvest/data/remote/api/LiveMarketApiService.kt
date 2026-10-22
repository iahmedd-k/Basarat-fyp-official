package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.live.LiveMarketStatusDto
import com.fyp.basarattradeinvest.data.remote.dto.live.RestQuotesResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Query
import retrofit2.http.Url

/**
 * Retrofit service for the live market REST endpoints.
 *
 * Both endpoints are documented in GET /api/v1/ws/protocol and
 * verified via GET /api/v1/ws/stats.
 */
interface LiveMarketApiService {

    /**
     * Bootstrap / discovery endpoint.
     * Returns market status, transport config, and WebSocket URL.
     * Call once at app start to confirm the WS URL and poll interval.
     */
    @GET("api/v1/market/live")
    suspend fun getLiveMarketStatus(): Response<LiveMarketStatusDto>

    /**
     * REST fallback quote cache.
     * Safe to poll; never scrapes PSX — served from Celery/Redis snapshot.
     * The [symbols] param is a comma-separated list (e.g. "SYS,LUCK,OGDC").
     * Omit [symbols] to receive the full board (limit 500).
     */
    @GET
    suspend fun getQuotes(
        @Url path: String,
        @Query("symbols") symbols: String? = null,
        @Query("limit") limit: Int = 500,
        @Query("offset") offset: Int = 0
    ): Response<RestQuotesResponseDto>
}
