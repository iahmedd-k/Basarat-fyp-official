package com.fyp.basarattradeinvest.feature.news

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.NewsRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import com.fyp.basarattradeinvest.domain.usecase.news.GetNewsAndEventsUseCase
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class NewsEventsViewModel(
    private val getNewsAndEventsUseCase: GetNewsAndEventsUseCase = GetNewsAndEventsUseCase(NewsRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<NewsEventsUiState>(NewsEventsUiState.Loading)
    val uiState: StateFlow<NewsEventsUiState> = _uiState.asStateFlow()

    private var currentCategory: String = "All"
    private var searchQuery: String = ""

    private var cachedNews: MutableList<NewsArticle> = mutableListOf()

    private var nextCursor: String? = null
    private var hasMoreNews: Boolean = false
    private var isLoadingMore: Boolean = false
    private var marketStatusText: String? = null

    private var searchJob: Job? = null
    private var refreshJob: Job? = null

    init {
        loadInitialData()
    }

    fun loadInitialData() {
        loadData(category = currentCategory, query = searchQuery)
    }

    fun loadData(
        category: String = currentCategory,
        query: String = searchQuery
    ) {
        currentCategory = category
        searchQuery = query

        viewModelScope.launch {
            _uiState.value = NewsEventsUiState.Loading

            // Fetch Market Status asynchronously
            val marketStatusResult = getNewsAndEventsUseCase.getMarketStatusText()
            marketStatusText = marketStatusResult.getOrNull()

            val newsResult = getNewsAndEventsUseCase.getNewsFeed(
                category = currentCategory,
                query = searchQuery,
                cursor = null,
                limit = 20
            )

            if (newsResult.isSuccess) {
                val newsPage = newsResult.getOrNull()
                cachedNews.clear()
                if (newsPage != null) {
                    cachedNews.addAll(newsPage.articles)
                    nextCursor = newsPage.nextCursor
                    hasMoreNews = newsPage.hasMore
                } else {
                    nextCursor = null
                    hasMoreNews = false
                }

                if (cachedNews.isEmpty()) {
                    _uiState.value = NewsEventsUiState.Empty(
                        activeCategory = currentCategory,
                        marketStatusText = marketStatusText
                    )
                } else {
                    _uiState.value = NewsEventsUiState.Success(
                        newsArticles = cachedNews.toList(),
                        activeCategory = currentCategory,
                        searchQuery = searchQuery,
                        nextCursor = nextCursor,
                        hasMore = hasMoreNews,
                        isLoadingMore = false,
                        isRefreshing = false,
                        marketStatusText = marketStatusText
                    )
                }
            } else {
                val errorMsg = newsResult.exceptionOrNull()?.message
                    ?: "Unable to load PSX news and corporate intelligence."
                _uiState.value = NewsEventsUiState.Error(errorMsg)
            }
        }
    }

    fun loadNextPage() {
        if (isLoadingMore || !hasMoreNews || nextCursor.isNullOrBlank()) return

        isLoadingMore = true
        val currentState = _uiState.value
        if (currentState is NewsEventsUiState.Success) {
            _uiState.value = currentState.copy(isLoadingMore = true)
        }

        viewModelScope.launch {
            val cursorToUse = nextCursor
            val result = getNewsAndEventsUseCase.getNewsFeed(
                category = currentCategory,
                query = searchQuery,
                cursor = cursorToUse,
                limit = 20
            )

            isLoadingMore = false
            if (result.isSuccess) {
                val page = result.getOrNull()
                if (page != null) {
                    nextCursor = page.nextCursor
                    hasMoreNews = page.hasMore

                    // Append without duplicates
                    val existingIds = cachedNews.map { it.id }.toSet()
                    val newUnique = page.articles.filter { it.id !in existingIds }
                    cachedNews.addAll(newUnique)

                    _uiState.value = NewsEventsUiState.Success(
                        newsArticles = cachedNews.toList(),
                        activeCategory = currentCategory,
                        searchQuery = searchQuery,
                        nextCursor = nextCursor,
                        hasMore = hasMoreNews,
                        isLoadingMore = false,
                        isRefreshing = false,
                        marketStatusText = marketStatusText
                    )
                }
            } else {
                if (currentState is NewsEventsUiState.Success) {
                    _uiState.value = currentState.copy(isLoadingMore = false)
                }
            }
        }
    }

    fun refreshNews() {
        if (refreshJob?.isActive == true) return

        val currentState = _uiState.value
        if (currentState is NewsEventsUiState.Success) {
            _uiState.value = currentState.copy(isRefreshing = true, refreshMessage = "Refreshing...")
        }

        refreshJob = viewModelScope.launch {
            // 1. Trigger manual refresh
            val triggerResult = getNewsAndEventsUseCase.triggerRefresh(force = false)
            if (triggerResult.isSuccess) {
                var attempts = 0
                while (attempts < 4) {
                    delay(1500)
                    attempts++
                    val statusRes = getNewsAndEventsUseCase.getRefreshStatus()
                    if (statusRes.isSuccess) {
                        val state = statusRes.getOrNull()?.state
                        if (state == "idle" || state == "completed") {
                            break
                        }
                    }
                }
            }

            // 2. Reload latest feed
            val newsResult = getNewsAndEventsUseCase.getNewsFeed(
                category = currentCategory,
                query = searchQuery,
                cursor = null,
                limit = 20
            )

            if (newsResult.isSuccess) {
                val page = newsResult.getOrNull()
                cachedNews.clear()
                if (page != null) {
                    cachedNews.addAll(page.articles)
                    nextCursor = page.nextCursor
                    hasMoreNews = page.hasMore
                }
            }

            if (cachedNews.isEmpty()) {
                _uiState.value = NewsEventsUiState.Empty(
                    activeCategory = currentCategory,
                    marketStatusText = marketStatusText
                )
            } else {
                _uiState.value = NewsEventsUiState.Success(
                    newsArticles = cachedNews.toList(),
                    activeCategory = currentCategory,
                    searchQuery = searchQuery,
                    nextCursor = nextCursor,
                    hasMore = hasMoreNews,
                    isLoadingMore = false,
                    isRefreshing = false,
                    marketStatusText = marketStatusText,
                    refreshMessage = "Updated successfully"
                )
            }
        }
    }

    fun setCategory(category: String) {
        if (currentCategory.equals(category, ignoreCase = true)) return
        loadData(category = category, query = searchQuery)
    }

    fun onSearchQueryChanged(query: String) {
        searchJob?.cancel()
        searchJob = viewModelScope.launch {
            delay(400) // Debounce typing
            if (searchQuery != query) {
                loadData(category = currentCategory, query = query)
            }
        }
    }

    fun retry() {
        loadData(category = currentCategory, query = searchQuery)
    }
}
