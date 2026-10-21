package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.sentiment.MarketSentimentResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentHistoryPointDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentHistoryResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentNewsItemDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentNewsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentResponseDto
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentimentOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistory
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistoryPoint
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsItem
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsPage
import com.fyp.basarattradeinvest.domain.model.sentiment.StockSentiment

/**
 * SentimentDtoMapper
 *
 * Maps Sentiment API DTOs to domain models.
 * Field-by-field mapping verified against OpenAPI schema.
 * All nullable fields preserved as nullable in domain models.
 */
object SentimentDtoMapper {

    // ─── Stock Sentiment ───────────────────────────────────────────────────────

    fun mapStockSentiment(dto: SentimentResponseDto): StockSentiment {
        val newsCount = dto.sourceBreakdown?.get("news") ?: 0
        val communityCount = dto.sourceBreakdown?.get("community") ?: 0
        return StockSentiment(
            symbol = dto.symbol.orEmpty(),
            score = dto.score,
            label = dto.label ?: "neutral",
            articleCount = dto.articleCount,
            trend = dto.trend ?: "stable",
            newsSourceCount = newsCount,
            communitySourceCount = communityCount
        )
    }

    // ─── Sentiment History ─────────────────────────────────────────────────────

    fun mapSentimentHistory(dto: SentimentHistoryResponseDto): SentimentHistory {
        return SentimentHistory(
            symbol = dto.symbol.orEmpty(),
            period = dto.period ?: "1M",
            data = dto.data.orEmpty().map { mapHistoryPoint(it) }
        )
    }

    private fun mapHistoryPoint(dto: SentimentHistoryPointDto): SentimentHistoryPoint {
        return SentimentHistoryPoint(
            date = dto.date.orEmpty(),
            score = dto.score,
            label = dto.label ?: "neutral",
            articleCount = dto.articleCount,
            positiveRatio = dto.positiveRatio,
            neutralRatio = dto.neutralRatio,
            negativeRatio = dto.negativeRatio,
            trend = dto.trend
        )
    }

    // ─── Sentiment News ────────────────────────────────────────────────────────

    fun mapSentimentNewsPage(dto: SentimentNewsResponseDto): SentimentNewsPage {
        return SentimentNewsPage(
            symbol = dto.symbol.orEmpty(),
            items = dto.items.orEmpty().map { mapNewsItem(it) },
            total = dto.total,
            page = dto.page,
            limit = dto.limit
        )
    }

    private fun mapNewsItem(dto: SentimentNewsItemDto): SentimentNewsItem {
        return SentimentNewsItem(
            id = dto.id ?: dto.url.orEmpty(),
            title = dto.title.orEmpty(),
            source = dto.source,
            publishedAt = dto.publishedAt,
            url = dto.url,
            sentiment = dto.sentiment,
            sentimentScore = dto.sentimentScore,
            sentimentModel = dto.sentimentModel
        )
    }

    // ─── Market Sentiment Overview ─────────────────────────────────────────────

    fun mapMarketSentimentOverview(dto: MarketSentimentResponseDto): MarketSentimentOverview {
        val dist = dto.scoreDistribution
        return MarketSentimentOverview(
            marketMood = dto.marketMood ?: "neutral",
            overallScore = dto.overallScore,
            articleCount = dto.articleCount,
            communityPostCount = dto.communityPostCount,
            advancing = dto.advancing,
            declining = dto.declining,
            unchanged = dto.unchanged,
            advanceDeclineRatio = dto.advanceDeclineRatio,
            newsSentimentAvg = dto.newsSentimentAvg,
            communitySentimentAvg = dto.communitySentimentAvg,
            scoreDistributionPositive = dist?.get("positive") ?: 0,
            scoreDistributionNeutral = dist?.get("neutral") ?: 0,
            scoreDistributionNegative = dist?.get("negative") ?: 0
        )
    }

    // ─── Bridge News Article to Sentiment Item ────────────────────────────────
    fun mapNewsArticleToSentimentItem(dto: com.fyp.basarattradeinvest.data.remote.dto.news.NewsArticleResponseDto): SentimentNewsItem {
        val label = dto.sentiment?.label?.trim()
        val rawScore = dto.sentiment?.score?.toFloat()
        val computedScore = rawScore ?: when (label?.lowercase(java.util.Locale.ROOT)) {
            "positive", "bullish" -> 0.75f
            "negative", "bearish" -> -0.75f
            else -> 0.0f
        }
        val normalizedLabel = when (label?.lowercase(java.util.Locale.ROOT)) {
            "positive", "bullish" -> "BULLISH"
            "negative", "bearish" -> "BEARISH"
            else -> "NEUTRAL"
        }
        return SentimentNewsItem(
            id = dto.id,
            title = dto.title,
            source = dto.source?.name,
            publishedAt = dto.publishedAt,
            url = dto.url ?: dto.externalUrl,
            sentiment = normalizedLabel,
            sentimentScore = computedScore,
            sentimentModel = dto.sentiment?.method ?: "finbert"
        )
    }

    // ─── Bridge Market Breadth to Market Sentiment Overview ───────────────────
    fun mapMarketOverviewDto(dto: com.fyp.basarattradeinvest.data.remote.dto.market.SentimentOverviewDto): MarketSentimentOverview {
        val mood = dto.marketMood ?: "neutral"
        val score = when (mood.lowercase(java.util.Locale.ROOT)) {
            "strongly_bullish" -> 0.85f
            "bullish" -> 0.50f
            "bearish" -> -0.50f
            "strongly_bearish" -> -0.75f
            else -> 0.0f
        }
        return MarketSentimentOverview(
            marketMood = mood,
            overallScore = score,
            articleCount = 0,
            communityPostCount = 0,
            advancing = dto.advancing ?: 0,
            declining = dto.declining ?: 0,
            unchanged = dto.unchanged ?: 0,
            advanceDeclineRatio = dto.advanceDeclineRatio?.toFloat() ?: 0f,
            newsSentimentAvg = score,
            communitySentimentAvg = 0f,
            scoreDistributionPositive = (dto.gainersPct ?: 0.0).toInt(),
            scoreDistributionNeutral = 0,
            scoreDistributionNegative = (dto.losersPct ?: 0.0).toInt()
        )
    }
}
