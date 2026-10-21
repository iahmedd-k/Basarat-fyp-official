package com.fyp.basarattradeinvest.domain.usecase.news

import com.fyp.basarattradeinvest.domain.model.market.CorporateEvent
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import com.fyp.basarattradeinvest.domain.model.news.NewsFeedPage
import com.fyp.basarattradeinvest.domain.model.news.RefreshResult
import com.fyp.basarattradeinvest.domain.model.news.RefreshStatus
import com.fyp.basarattradeinvest.domain.repository.NewsRepository

class GetNewsAndEventsUseCase(
    private val repository: NewsRepository
) {
    suspend fun getNewsFeed(
        category: String = "All",
        query: String = "",
        cursor: String? = null,
        limit: Int = 20
    ): Result<NewsFeedPage> {
        return repository.getNewsFeed(category, query, cursor, limit)
    }

    suspend fun getNews(category: String = "All", query: String = ""): Result<List<NewsArticle>> {
        return repository.getNewsArticles(category, query)
    }

    suspend fun getEvents(
        category: String = "All",
        query: String = "",
        symbol: String? = null,
        fromDate: String? = null,
        toDate: String? = null
    ): Result<List<CorporateEvent>> {
        return repository.getCorporateEvents(category, query, symbol, fromDate, toDate)
    }

    suspend fun getNewsArticle(articleId: String): Result<NewsArticle> {
        return repository.getNewsArticle(articleId)
    }

    suspend fun getStockNews(symbol: String, cursor: String? = null, limit: Int = 20): Result<NewsFeedPage> {
        return repository.getStockNews(symbol, cursor, limit)
    }

    suspend fun triggerRefresh(force: Boolean = false): Result<RefreshResult> {
        return repository.triggerManualRefresh(force)
    }

    suspend fun getRefreshStatus(): Result<RefreshStatus> {
        return repository.getRefreshStatus()
    }

    suspend fun getMarketStatusText(): Result<String?> {
        return repository.getMarketStatusText()
    }
}
