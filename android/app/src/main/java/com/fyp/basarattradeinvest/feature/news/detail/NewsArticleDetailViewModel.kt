package com.fyp.basarattradeinvest.feature.news.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.NewsRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.news.GetNewsAndEventsUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class NewsArticleDetailViewModel(
    private val getNewsAndEventsUseCase: GetNewsAndEventsUseCase = GetNewsAndEventsUseCase(NewsRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<NewsArticleDetailUiState>(NewsArticleDetailUiState.Loading)
    val uiState: StateFlow<NewsArticleDetailUiState> = _uiState.asStateFlow()

    private var currentArticleId: String = ""
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L

    fun ensureLoaded(articleId: String) {
        val state = _uiState.value
        val isSameArticle = currentArticleId == articleId && state is NewsArticleDetailUiState.Success
        val shouldLoad = !isSameArticle || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
        if (shouldLoad) {
            loadArticle(articleId)
        }
    }

    fun loadArticle(articleId: String) {
        currentArticleId = articleId
        viewModelScope.launch {
            val currentState = _uiState.value
            // Compare against the article the cached state actually holds; this VM is
            // activity-scoped, so a previous article's Success must not skip this load.
            val isSameArticle = currentState is NewsArticleDetailUiState.Success &&
                currentState.article.id == articleId
            if (isSameArticle && System.currentTimeMillis() - lastSuccessfulFetchAt <= freshnessWindowMs) {
                return@launch
            }
            _uiState.value = NewsArticleDetailUiState.Loading
            val result = getNewsAndEventsUseCase.getNewsArticle(articleId)
            result.fold(
                onSuccess = { article ->
                    lastSuccessfulFetchAt = System.currentTimeMillis()
                    _uiState.value = NewsArticleDetailUiState.Success(article)
                },
                onFailure = { error ->
                    _uiState.value = NewsArticleDetailUiState.Error(
                        error.message ?: "Failed to load article detail"
                    )
                }
            )
        }
    }

    fun retry() {
        if (currentArticleId.isNotBlank()) {
            loadArticle(currentArticleId)
        }
    }
}
