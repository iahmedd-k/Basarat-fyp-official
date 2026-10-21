package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentimentOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistory
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsPage
import com.fyp.basarattradeinvest.domain.model.sentiment.StockSentiment

/**
 * SentimentRepository
 *
 * Repository interface for all Sentiment API operations.
 * Implementations in data/repository/SentimentRepositoryImpl.
 */
interface SentimentRepository {

    /**
     * Fetch FinBERT stock sentiment for the given symbol.
     * @param symbol PSX ticker
     * @param days Rolling window (1–90). Pass null to use backend default (7).
     */
    suspend fun getStockSentiment(symbol: String, days: Int? = null): Result<StockSentiment>

    /**
     * Fetch historical sentiment time series.
     * @param symbol PSX ticker
     * @param period One of 1D/1W/1M/3M/6M/1Y. Null uses backend default (1M).
     * @param limit  Max points (1–500). Null uses backend default (100).
     */
    suspend fun getSentimentHistory(
        symbol: String,
        period: String? = null,
        limit: Int? = null
    ): Result<SentimentHistory>

    /**
     * Fetch paginated news with sentiment annotations.
     * @param symbol     PSX ticker
     * @param page       Page number (≥1)
     * @param limit      Items per page (1–100)
     * @param sentiment  Optional filter: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | null
     */
    suspend fun getSentimentNews(
        symbol: String,
        page: Int,
        limit: Int,
        sentiment: String? = null
    ): Result<SentimentNewsPage>

    /**
     * Fetch market-wide sentiment overview.
     */
    suspend fun getMarketSentiment(): Result<MarketSentimentOverview>
}
