package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.news.EventsCalendarResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsArticleResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsRefreshResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsRefreshStatusResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.SourcesResponseDto
import com.google.gson.JsonObject
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit service definition for BASARAT News & Events endpoints.
 * Defined strictly according to OpenAPI / Swagger contract at:
 * http://16.16.26.247:8000/api/v1/openapi.json
 */
interface NewsApiService {

    @GET("api/v1/news")
    suspend fun getNewsFeed(
        @Query("row") row: String = "news",
        @Query("symbol") symbol: String? = null,
        @Query("sentiment") sentiment: String? = null,
        @Query("source") source: String? = null,
        @Query("source_type") sourceType: String? = null,
        @Query("event_type") eventType: String? = null,
        @Query("q") query: String? = null,
        @Query("limit") limit: Int = 20,
        @Query("cursor") cursor: String? = null
    ): Response<NewsListResponseDto>

    @POST("api/v1/news/refresh")
    suspend fun refreshNews(
        @Query("force") force: Boolean? = null
    ): Response<NewsRefreshResponseDto>

    @GET("api/v1/news/refresh/status")
    suspend fun getRefreshStatus(): Response<NewsRefreshStatusResponseDto>

    @GET("api/v1/news/market-status")
    suspend fun getMarketStatus(): Response<JsonObject>

    @GET("api/v1/news/sources")
    suspend fun getNewsSources(): Response<SourcesResponseDto>

    @GET("api/v1/news/{article_id}")
    suspend fun getNewsArticle(
        @Path("article_id") articleId: String
    ): Response<NewsArticleResponseDto>

    @GET("api/v1/stocks/{symbol}/news")
    suspend fun getStockNews(
        @Path("symbol") symbol: String,
        @Query("sentiment") sentiment: String? = null,
        @Query("source_type") sourceType: String? = null,
        @Query("event_type") eventType: String? = null,
        @Query("limit") limit: Int = 20,
        @Query("cursor") cursor: String? = null
    ): Response<NewsListResponseDto>

    @GET("api/v1/events/calendar")
    suspend fun getEventsCalendar(
        @Query("from") fromDate: String? = null,
        @Query("to") toDate: String? = null,
        @Query("event_type") eventType: String? = null,
        @Query("symbol") symbol: String? = null
    ): Response<EventsCalendarResponseDto>
}
