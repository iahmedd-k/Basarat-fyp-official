package com.fyp.basarattradeinvest.domain.usecase.sentiment

import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentimentOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistory
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsPage
import com.fyp.basarattradeinvest.domain.model.sentiment.StockSentiment
import com.fyp.basarattradeinvest.domain.repository.SentimentRepository

/**
 * GetStockSentimentUseCase
 *
 * Fetches FinBERT sentiment analysis for a PSX stock symbol.
 * @param days Rolling window (1–90). Null uses backend default (7 days).
 */
class GetStockSentimentUseCase(
    private val repository: SentimentRepository
) {
    suspend operator fun invoke(symbol: String, days: Int? = null): Result<StockSentiment> {
        return repository.getStockSentiment(symbol, days)
    }
}

/**
 * GetSentimentHistoryUseCase
 *
 * Fetches the historical daily sentiment time series for a PSX stock.
 * @param period One of 1D/1W/1M/3M/6M/1Y. Null uses backend default (1M).
 * @param limit  Max data points (1–500). Null uses backend default (100).
 */
class GetSentimentHistoryUseCase(
    private val repository: SentimentRepository
) {
    suspend operator fun invoke(
        symbol: String,
        period: String? = null,
        limit: Int? = null
    ): Result<SentimentHistory> {
        return repository.getSentimentHistory(symbol, period, limit)
    }
}

/**
 * GetSentimentNewsUseCase
 *
 * Fetches paginated news articles with FinBERT sentiment annotations.
 * @param page       Page number (≥1)
 * @param limit      Items per page (1–100)
 * @param sentiment  Optional filter: "POSITIVE" | "NEGATIVE" | "NEUTRAL" | null
 */
class GetSentimentNewsUseCase(
    private val repository: SentimentRepository
) {
    suspend operator fun invoke(
        symbol: String,
        page: Int = 1,
        limit: Int = 20,
        sentiment: String? = null
    ): Result<SentimentNewsPage> {
        return repository.getSentimentNews(symbol, page, limit, sentiment)
    }
}

/**
 * GetMarketSentimentOverviewUseCase
 *
 * Fetches market-wide FinBERT/NLP sentiment overview.
 * (distinct from GetMarketSentimentUseCase which uses /api/v1/market/sentiment-overview)
 */
class GetMarketSentimentOverviewUseCase(
    private val repository: SentimentRepository
) {
    suspend operator fun invoke(): Result<MarketSentimentOverview> {
        return repository.getMarketSentiment()
    }
}
