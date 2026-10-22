package com.fyp.basarattradeinvest.feature.news

import com.fyp.basarattradeinvest.domain.model.news.NewsArticle

sealed interface NewsEventsUiState {
    data object Loading : NewsEventsUiState

    data class Success(
        val newsArticles: List<NewsArticle>,
        val activeCategory: String = "All",
        val searchQuery: String = "",
        val nextCursor: String? = null,
        val hasMore: Boolean = false,
        val isLoadingMore: Boolean = false,
        val isRefreshing: Boolean = false,
        val marketStatusText: String? = null,
        val refreshMessage: String? = null
    ) : NewsEventsUiState

    data class Empty(
        val activeCategory: String = "All",
        val marketStatusText: String? = null
    ) : NewsEventsUiState

    data class Error(val message: String) : NewsEventsUiState
}
