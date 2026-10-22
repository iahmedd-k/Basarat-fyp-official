package com.fyp.basarattradeinvest.domain.model.news

data class NewsArticle(
    val id: String,
    val symbol: String,
    val hasDividend: Boolean = false,
    val source: String,
    val timestamp: String,
    val sentimentScore: Double,
    val sentimentLabel: String, // "Bullish", "Bearish", "Neutral"
    val headline: String,
    val snippet: String,
    val category: String = "All",
    val url: String? = null,
    val externalUrl: String? = null,
    val isOfficial: Boolean = false,
    val symbols: List<String> = emptyList(),
    val publishedAt: String? = null
)

enum class NewsTab {
    GENERAL_NEWS,
    CORPORATE_EVENTS
}
