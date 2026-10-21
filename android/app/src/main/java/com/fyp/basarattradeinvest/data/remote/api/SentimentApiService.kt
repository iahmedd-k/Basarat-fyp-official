package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.sentiment.MarketSentimentResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentHistoryResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentNewsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * SentimentApiService
 *
 * Retrofit interface for all four Sentiment API endpoints.
 * Uses the shared Retrofit instance from NetworkClient (no separate client).
 * Authentication is handled by the existing AuthInterceptor.
 *
 * Endpoint paths verified against live OpenAPI spec at:
 * http://16.16.26.247:8000/api/v1/openapi.json
 */
interface SentimentApiService {

    /**
     * GET /api/v1/sentiment/{symbol}
     *
     * Returns FinBERT sentiment analysis for a given PSX stock symbol.
     *
     * @param symbol   PSX ticker symbol (e.g. "OGDC", "LUCK")
     * @param days     Rolling window in days. Min=1, Max=90, Default=7. Optional.
     */
    @GET("api/v1/sentiment/{symbol}")
    suspend fun getStockSentiment(
        @Path("symbol") symbol: String,
        @Query("days") days: Int? = null
    ): Response<SentimentResponseDto>

    /**
     * GET /api/v1/sentiment/{symbol}/history
     *
     * Returns historical daily sentiment time series for a stock.
     *
     * @param symbol   PSX ticker symbol
     * @param period   One of: 1D, 1W, 1M, 3M, 6M, 1Y. Default=1M. Optional.
     * @param limit    Max data points to return. Min=1, Max=500, Default=100. Optional.
     */
    @GET("api/v1/sentiment/{symbol}/history")
    suspend fun getSentimentHistory(
        @Path("symbol") symbol: String,
        @Query("period") period: String? = null,
        @Query("limit") limit: Int? = null
    ): Response<SentimentHistoryResponseDto>

    /**
     * GET /api/v1/sentiment/{symbol}/news
     *
     * Returns paginated news articles with FinBERT sentiment annotations.
     *
     * @param symbol     PSX ticker symbol
     * @param page       Page number, min=1, default=1
     * @param limit      Items per page, min=1, max=100, default=20
     * @param sentiment  Optional filter: "POSITIVE" | "NEGATIVE" | "NEUTRAL"
     */
    @GET("api/v1/sentiment/{symbol}/news")
    suspend fun getSentimentNews(
        @Path("symbol") symbol: String,
        @Query("page") page: Int,
        @Query("limit") limit: Int,
        @Query("sentiment") sentiment: String? = null
    ): Response<SentimentNewsResponseDto>

    /**
     * GET /api/v1/sentiment/market-overview
     *
     * Returns market-wide FinBERT/NLP sentiment overview.
     * No path or query parameters required.
     */
    @GET("api/v1/sentiment/market-overview")
    suspend fun getMarketSentiment(): Response<MarketSentimentResponseDto>
}
