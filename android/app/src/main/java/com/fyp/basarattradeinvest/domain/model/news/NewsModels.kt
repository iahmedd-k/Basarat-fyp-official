package com.fyp.basarattradeinvest.domain.model.news

data class NewsFeedPage(
    val articles: List<NewsArticle>,
    val nextCursor: String?,
    val hasMore: Boolean,
    val total: Int? = null,
    val lastUpdatedAt: String? = null
)

data class RefreshResult(
    val status: String,
    val refreshAvailable: Boolean,
    val nextRefreshAt: String?,
    val articlesInserted: Int,
    val retryAfterSeconds: Int?
)

data class RefreshStatus(
    val state: String, // "idle" | "running" | "completed" | "failed"
    val lastSuccessAt: String?,
    val newArticles: Int
)
