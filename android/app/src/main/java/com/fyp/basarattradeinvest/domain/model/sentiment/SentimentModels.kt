package com.fyp.basarattradeinvest.domain.model.sentiment

// ─────────────────────────────────────────────────────────────────────────────
// Domain models for the Sentiment Analysis module.
// All field names mirror the verified OpenAPI schema semantics.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Stock-level sentiment summary.
 * score: -1.0 (fully bearish) to +1.0 (fully bullish)
 * label: "positive" | "negative" | "neutral"
 * trend: "improving" | "declining" | "stable"
 * newsSourceCount / communitySourceCount: from source_breakdown map
 */
data class StockSentiment(
    val symbol: String,
    val score: Float,
    val label: String,
    val articleCount: Int,
    val trend: String,
    val newsSourceCount: Int,
    val communitySourceCount: Int
)

/**
 * Single point in the historical sentiment time series.
 * date: "YYYY-MM-DD"
 * score: -1.0 to +1.0
 */
data class SentimentHistoryPoint(
    val date: String,
    val score: Float,
    val label: String,
    val articleCount: Int,
    val positiveRatio: Float?,
    val neutralRatio: Float?,
    val negativeRatio: Float?,
    val trend: String?
)

/**
 * Full historical response for a symbol.
 */
data class SentimentHistory(
    val symbol: String,
    val period: String,
    val data: List<SentimentHistoryPoint>
)

/**
 * Single news article with FinBERT sentiment annotation.
 * No image field — API does not return one.
 * sentimentScore: -1.0 to +1.0, nullable
 */
data class SentimentNewsItem(
    val id: String,
    val title: String,
    val source: String?,
    val publishedAt: String?,
    val url: String?,
    val sentiment: String?,
    val sentimentScore: Float?,
    val sentimentModel: String?
)

/**
 * Paginated news response.
 * hasMore = (page * limit) < total
 */
data class SentimentNewsPage(
    val symbol: String,
    val items: List<SentimentNewsItem>,
    val total: Int,
    val page: Int,
    val limit: Int
) {
    val hasMore: Boolean get() = (page * limit) < total
}

/**
 * Market-wide sentiment overview.
 * marketMood: "bullish" | "bearish" | "neutral"
 * overallScore: -1.0 to +1.0
 * scoreDistributionPositive / Neutral / Negative: from score_distribution map
 */
data class MarketSentimentOverview(
    val marketMood: String,
    val overallScore: Float,
    val articleCount: Int,
    val communityPostCount: Int,
    val advancing: Int,
    val declining: Int,
    val unchanged: Int,
    val advanceDeclineRatio: Float,
    val newsSentimentAvg: Float,
    val communitySentimentAvg: Float,
    val scoreDistributionPositive: Int,
    val scoreDistributionNeutral: Int,
    val scoreDistributionNegative: Int
)
