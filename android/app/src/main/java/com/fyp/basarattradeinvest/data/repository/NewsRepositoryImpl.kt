package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.mapper.NewsDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.NewsApiService
import com.fyp.basarattradeinvest.domain.model.market.CorporateEvent
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import com.fyp.basarattradeinvest.domain.model.news.NewsFeedPage
import com.fyp.basarattradeinvest.domain.model.news.RefreshResult
import com.fyp.basarattradeinvest.domain.model.news.RefreshStatus
import com.fyp.basarattradeinvest.domain.repository.NewsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.Locale

class NewsRepositoryImpl(
    private val apiService: NewsApiService = NetworkClient.newsApiService
) : NewsRepository {

    override suspend fun getNewsFeed(
        category: String,
        query: String,
        cursor: String?,
        limit: Int
    ): Result<NewsFeedPage> = withContext(Dispatchers.IO) {
        try {
            val normalizedCat = category.trim().lowercase(Locale.ROOT)
            val eventTypeParam = when (normalizedCat) {
                "earnings" -> "earnings"
                "dividends" -> "dividend"
                else -> null
            }
            val sourceTypeParam = when (normalizedCat) {
                "corporate" -> "official"
                else -> null
            }
            val sentimentParam = when (normalizedCat) {
                "bullish" -> "bullish"
                "bearish" -> "bearish"
                "neutral" -> "neutral"
                else -> null
            }

            // Combine category filter and text search if needed
            val effectiveQuery = when {
                query.isNotBlank() -> query.trim()
                normalizedCat !in listOf("all", "", "corporate", "earnings", "dividends", "bullish", "bearish", "neutral") -> category.trim()
                else -> null
            }

            val response = apiService.getNewsFeed(
                query = effectiveQuery,
                eventType = eventTypeParam,
                sourceType = sourceTypeParam,
                sentiment = sentimentParam,
                limit = limit,
                cursor = cursor
            )

            if (response.isSuccessful) {
                val body = response.body()
                val articles = body?.items?.map { NewsDtoMapper.mapArticleDtoToDomain(it) } ?: emptyList()
                val nextCursor = body?.nextCursor
                val hasMore = body?.hasMore ?: (nextCursor != null)
                val total = body?.total
                val lastUpdated = body?.lastUpdatedAt

                Result.success(
                    NewsFeedPage(
                        articles = articles,
                        nextCursor = nextCursor,
                        hasMore = hasMore,
                        total = total,
                        lastUpdatedAt = lastUpdated
                    )
                )
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getNewsArticles(category: String, query: String): Result<List<NewsArticle>> {
        val pageResult = getNewsFeed(category = category, query = query, limit = 30)
        return pageResult.map { it.articles }
    }

    override suspend fun getCorporateEvents(
        category: String,
        query: String,
        symbol: String?,
        fromDate: String?,
        toDate: String?
    ): Result<List<CorporateEvent>> = withContext(Dispatchers.IO) {
        try {
            val normalizedCat = category.trim().lowercase(Locale.ROOT)
            val eventTypeParam = when (normalizedCat) {
                "earnings" -> "earnings"
                "dividends" -> "dividend"
                "sbp" -> "sbp_monetary_policy"
                else -> null
            }

            val response = apiService.getEventsCalendar(
                fromDate = fromDate,
                toDate = toDate,
                eventType = eventTypeParam,
                symbol = symbol
            )

            var events = if (response.isSuccessful) {
                val body = response.body()
                body?.items?.map { NewsDtoMapper.mapEventDtoToDomain(it) } ?: emptyList()
            } else {
                emptyList()
            }

            // Fallback: If events calendar is empty or requires authentication,
            // extract corporate announcements from news feed (isOfficial or has eventType or source is official)
            if (events.isEmpty()) {
                val newsRes = apiService.getNewsFeed(
                    eventType = eventTypeParam,
                    limit = 30
                )
                if (newsRes.isSuccessful) {
                    val rawItems = newsRes.body()?.items ?: emptyList()
                    val corporateItems = rawItems.filter {
                        it.isOfficial == true ||
                                it.source?.type == "official" ||
                                (it.eventType != null && it.eventType != "other")
                    }
                    val mappedEvents = corporateItems.map { item ->
                        val sym = item.symbols?.firstOrNull()?.symbol ?: "PSX"
                        val comp = item.symbols?.firstOrNull()?.name ?: sym
                        CorporateEvent(
                            id = item.id,
                            eventType = (item.eventType ?: "ANNOUNCEMENT").uppercase(Locale.ROOT).replace("_", " "),
                            symbol = sym,
                            companyName = comp,
                            eventDate = NewsDtoMapper.formatRelativeTime(item.publishedAt ?: item.createdAt),
                            description = item.title,
                            bookClosure = item.summary.orEmpty(),
                            sourceNotice = item.source?.name ?: "PSX Official Notice",
                            category = item.eventType ?: "corporate",
                            sourceUrl = item.url ?: item.externalUrl
                        )
                    }
                    events = mappedEvents
                }
            }

            // If query is present, filter locally
            if (query.isNotBlank()) {
                val q = query.trim().lowercase(Locale.ROOT)
                events = events.filter {
                    it.symbol.lowercase(Locale.ROOT).contains(q) ||
                            it.companyName.lowercase(Locale.ROOT).contains(q) ||
                            it.description.lowercase(Locale.ROOT).contains(q) ||
                            it.eventType.lowercase(Locale.ROOT).contains(q)
                }
            }

            Result.success(events)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getNewsArticle(articleId: String): Result<NewsArticle> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getNewsArticle(articleId)
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    Result.success(NewsDtoMapper.mapArticleDtoToDomain(body))
                } else {
                    Result.failure(Exception("Article details not found"))
                }
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getStockNews(
        symbol: String,
        cursor: String?,
        limit: Int
    ): Result<NewsFeedPage> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getStockNews(
                symbol = symbol,
                limit = limit,
                cursor = cursor
            )
            if (response.isSuccessful) {
                val body = response.body()
                val articles = body?.items?.map { NewsDtoMapper.mapArticleDtoToDomain(it) } ?: emptyList()
                val nextCursor = body?.nextCursor
                val hasMore = body?.hasMore ?: (nextCursor != null)
                val total = body?.total

                Result.success(
                    NewsFeedPage(
                        articles = articles,
                        nextCursor = nextCursor,
                        hasMore = hasMore,
                        total = total,
                        lastUpdatedAt = body?.lastUpdatedAt
                    )
                )
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun triggerManualRefresh(force: Boolean): Result<RefreshResult> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.refreshNews(force = force)
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    Result.success(
                        RefreshResult(
                            status = body.status,
                            refreshAvailable = body.refreshAvailable ?: true,
                            nextRefreshAt = body.nextRefreshAt,
                            articlesInserted = body.articlesInserted ?: 0,
                            retryAfterSeconds = body.retryAfterSeconds
                        )
                    )
                } else {
                    Result.failure(Exception("Empty refresh response"))
                }
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getRefreshStatus(): Result<RefreshStatus> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getRefreshStatus()
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    Result.success(
                        RefreshStatus(
                            state = body.state,
                            lastSuccessAt = body.lastSuccessAt,
                            newArticles = body.newArticles ?: 0
                        )
                    )
                } else {
                    Result.failure(Exception("Empty refresh status"))
                }
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getMarketStatusText(): Result<String?> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getMarketStatus()
            if (response.isSuccessful) {
                val json = response.body()
                val window = json?.get("market_window")?.asString
                val timePkt = json?.get("current_time_pkt")?.asString
                val text = if (!window.isNullOrBlank()) {
                    "Market: $window" + (if (!timePkt.isNullOrBlank()) " • $timePkt" else "")
                } else null
                Result.success(text)
            } else {
                Result.success(null)
            }
        } catch (_: Exception) {
            Result.success(null)
        }
    }
}
