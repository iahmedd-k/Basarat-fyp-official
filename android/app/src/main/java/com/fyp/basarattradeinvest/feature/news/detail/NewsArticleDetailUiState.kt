package com.fyp.basarattradeinvest.feature.news.detail

import com.fyp.basarattradeinvest.domain.model.news.NewsArticle

sealed interface NewsArticleDetailUiState {
    data object Loading : NewsArticleDetailUiState
    data class Success(val article: NewsArticle) : NewsArticleDetailUiState
    data class Error(val message: String) : NewsArticleDetailUiState
}
