package com.fyp.basarattradeinvest.data.remote.dto.sentiment

import com.google.gson.annotations.SerializedName

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/sentiment/{symbol}
// ─────────────────────────────────────────────────────────────────────────────

/**
 * SentimentResponseDto
 *
 * Exact mapping of the SentimentResponse OpenAPI schema.
 * score: -1.0 (bearish) to +1.0 (bullish)
 * label: "positive" | "negative" | "neutral"
 * trend: "improving" | "declining" | "stable"
 * source_breakdown: e.g. {"news": 8, "community": 4}
 * daily_scores: array of {date, score, count} objects
 */
data class SentimentResponseDto(
    @SerializedName("symbol")
    val symbol: String? = null,

    @SerializedName("score")
    val score: Float = 0f,

    @SerializedName("label")
    val label: String? = null,

    @SerializedName("article_count")
    val articleCount: Int = 0,

    @SerializedName("trend")
    val trend: String? = null,

    @SerializedName("source_breakdown")
    val sourceBreakdown: Map<String, Int>?,

    @SerializedName("daily_scores")
    val dailyScores: List<Map<String, Any>>?
)

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/sentiment/{symbol}/history
// ─────────────────────────────────────────────────────────────────────────────

/**
 * SentimentHistoryResponseDto
 *
 * Exact mapping of the SentimentHistoryResponse OpenAPI schema.
 */
data class SentimentHistoryResponseDto(
    @SerializedName("symbol")
    val symbol: String? = null,

    @SerializedName("period")
    val period: String? = null,

    @SerializedName("data")
    val data: List<SentimentHistoryPointDto>? = null
)

/**
 * SentimentHistoryPointDto
 *
 * Single data point in the history time series.
 * date: "YYYY-MM-DD"
 * score: -1.0 to +1.0
 * label: "positive" | "negative" | "neutral"
 * positive_ratio / neutral_ratio / negative_ratio: nullable floats (0.0-1.0)
 * trend: nullable string
 */
data class SentimentHistoryPointDto(
    @SerializedName("date")
    val date: String? = null,

    @SerializedName("score")
    val score: Float = 0f,

    @SerializedName("label")
    val label: String? = null,

    @SerializedName("article_count")
    val articleCount: Int = 0,

    @SerializedName("positive_ratio")
    val positiveRatio: Float?,

    @SerializedName("neutral_ratio")
    val neutralRatio: Float?,

    @SerializedName("negative_ratio")
    val negativeRatio: Float?,

    @SerializedName("trend")
    val trend: String?
)

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/sentiment/{symbol}/news
// ─────────────────────────────────────────────────────────────────────────────

/**
 * SentimentNewsResponseDto
 *
 * Paginated news response.
 * Pagination: page-based. hasMore = (page * limit) < total
 */
data class SentimentNewsResponseDto(
    @SerializedName("symbol")
    val symbol: String? = null,

    @SerializedName("items")
    val items: List<SentimentNewsItemDto>? = null,

    @SerializedName("total")
    val total: Int = 0,

    @SerializedName("page")
    val page: Int = 0,

    @SerializedName("limit")
    val limit: Int = 0
)

/**
 * SentimentNewsItemDto
 *
 * Single news article with FinBERT sentiment.
 * No image field — do not render an image placeholder.
 * sentiment: "POSITIVE" | "NEGATIVE" | "NEUTRAL" (uppercase from API filter param)
 *            or lowercase — handle both in UI
 * sentiment_score: -1.0 to +1.0, nullable
 * url: nullable — only show open-in-browser if not null
 */
data class SentimentNewsItemDto(
    @SerializedName("id")
    val id: String? = null,

    @SerializedName("title")
    val title: String? = null,

    @SerializedName("source")
    val source: String?,

    @SerializedName("published_at")
    val publishedAt: String?,

    @SerializedName("url")
    val url: String?,

    @SerializedName("sentiment")
    val sentiment: String?,

    @SerializedName("sentiment_score")
    val sentimentScore: Float?,

    @SerializedName("sentiment_model")
    val sentimentModel: String?
)

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/v1/sentiment/market-overview
// ─────────────────────────────────────────────────────────────────────────────

/**
 * MarketSentimentResponseDto
 *
 * Exact mapping of the MarketSentimentResponse OpenAPI schema.
 * market_mood: "bullish" | "bearish" | "neutral"
 * overall_score: -1.0 to +1.0
 * score_distribution: {"positive": N, "neutral": M, "negative": K}
 */
data class MarketSentimentResponseDto(
    @SerializedName("market_mood")
    val marketMood: String? = null,

    @SerializedName("overall_score")
    val overallScore: Float = 0f,

    @SerializedName("article_count")
    val articleCount: Int = 0,

    @SerializedName("community_post_count")
    val communityPostCount: Int = 0,

    @SerializedName("advancing")
    val advancing: Int,

    @SerializedName("declining")
    val declining: Int,

    @SerializedName("unchanged")
    val unchanged: Int,

    @SerializedName("advance_decline_ratio")
    val advanceDeclineRatio: Float,

    @SerializedName("news_sentiment_avg")
    val newsSentimentAvg: Float = 0f,

    @SerializedName("community_sentiment_avg")
    val communitySentimentAvg: Float = 0f,

    @SerializedName("score_distribution")
    val scoreDistribution: Map<String, Int>?
)
