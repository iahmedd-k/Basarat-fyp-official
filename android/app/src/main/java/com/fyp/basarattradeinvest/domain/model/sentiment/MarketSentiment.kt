package com.fyp.basarattradeinvest.domain.model.sentiment

data class MarketSentiment(
    val overallScore: Int, // 0 to 100
    val sentimentLabel: String, // e.g. "Bullish", "Neutral", "Bearish"
    val positivePercent: Int,
    val neutralPercent: Int,
    val negativePercent: Int,
    val newsCount: Int = 0,
    val aiSummary: String = "",
    val advanceDeclineRatio: Double = 0.0,
    val advancing: Int = 0,
    val declining: Int = 0,
    val unchanged: Int = 0
)
