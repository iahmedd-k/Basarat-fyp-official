package com.fyp.basarattradeinvest.sentiment

import com.fyp.basarattradeinvest.data.mapper.SentimentDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.MarketApiService
import com.fyp.basarattradeinvest.data.remote.api.NewsApiService
import com.fyp.basarattradeinvest.data.remote.api.SentimentApiService
import com.fyp.basarattradeinvest.data.remote.dto.market.SentimentOverviewDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsArticleResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.SentimentInfoDto
import com.fyp.basarattradeinvest.data.remote.dto.news.SourceInfoDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.MarketSentimentResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentHistoryResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentNewsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.SentimentResponseDto
import com.fyp.basarattradeinvest.data.repository.SentimentRepositoryImpl
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Response

class SentimentModuleUnitTest {

    private lateinit var fakeSentimentApi: FakeSentimentApiService
    private lateinit var fakeNewsApi: FakeNewsApiService
    private lateinit var fakeMarketApi: FakeMarketApiService
    private lateinit var repository: SentimentRepositoryImpl

    @Before
    fun setUp() {
        fakeSentimentApi = FakeSentimentApiService()
        fakeNewsApi = FakeNewsApiService()
        fakeMarketApi = FakeMarketApiService()
        repository = SentimentRepositoryImpl(
            apiService = fakeSentimentApi,
            newsApiService = fakeNewsApi,
            marketApiService = fakeMarketApi
        )
    }

    @Test
    fun testMapNewsArticleToSentimentItem() {
        val dto = NewsArticleResponseDto(
            id = "news_1",
            title = "SYS Reports Record Profit",
            source = SourceInfoDto("mettis", "Mettis Global", "news"),
            publishedAt = "2026-09-25T10:00:00Z",
            url = "https://example.com/news/1",
            sentiment = SentimentInfoDto(
                label = "bullish",
                score = 0.85,
                method = "finbert"
            )
        )

        val item = SentimentDtoMapper.mapNewsArticleToSentimentItem(dto)
        assertEquals("news_1", item.id)
        assertEquals("SYS Reports Record Profit", item.title)
        assertEquals("Mettis Global", item.source)
        assertEquals("BULLISH", item.sentiment)
        assertEquals(0.85f, item.sentimentScore ?: 0f, 0.001f)
        assertEquals("finbert", item.sentimentModel)
    }

    @Test
    fun testMapMarketOverviewDto() {
        val dto = SentimentOverviewDto(
            marketMood = "strongly_bearish",
            advancing = 99,
            declining = 350,
            unchanged = 36,
            advanceDeclineRatio = 0.28,
            gainersPct = 20.0,
            losersPct = 70.0,
            sectorPerformance = null,
            topMovers = null
        )

        val overview = SentimentDtoMapper.mapMarketOverviewDto(dto)
        assertEquals("strongly_bearish", overview.marketMood)
        assertEquals(-0.75f, overview.overallScore, 0.001f)
        assertEquals(99, overview.advancing)
        assertEquals(350, overview.declining)
        assertEquals(0.28f, overview.advanceDeclineRatio, 0.001f)
    }

    @Test
    fun testGetStockSentimentFallbackToLiveNewsWhenZeroArticles() = runBlocking {
        // Dedicated API returns 0 articles (the issue in user's screenshot)
        fakeSentimentApi.stockSentimentResponse = Response.success(
            SentimentResponseDto(
                symbol = "SYS",
                score = 0.0f,
                label = "neutral",
                articleCount = 0,
                trend = "stable",
                sourceBreakdown = null,
                dailyScores = null
            )
        )

        // News API has 2 real FinBERT articles for SYS
        fakeNewsApi.stockNewsResponse = Response.success(
            NewsListResponseDto(
                items = listOf(
                    NewsArticleResponseDto(
                        id = "sys_1",
                        title = "SYS surges on cloud contracts",
                        sentiment = SentimentInfoDto("positive", 1.0, "finbert"),
                        publishedAt = "2026-09-25T10:00:00Z"
                    ),
                    NewsArticleResponseDto(
                        id = "sys_2",
                        title = "SYS healthy margin growth",
                        sentiment = SentimentInfoDto("bullish", 0.5, "finbert"),
                        publishedAt = "2026-09-26T10:00:00Z"
                    )
                )
            )
        )

        val result = repository.getStockSentiment("SYS", days = 7)
        assertTrue(result.isSuccess)
        val sentiment = result.getOrThrow()
        assertEquals("SYS", sentiment.symbol)
        assertEquals(2, sentiment.articleCount)
        assertEquals("BULLISH", sentiment.label)
        assertEquals(0.75f, sentiment.score, 0.001f)
    }

    @Test
    fun testGetSentimentHistorySynthesizesChartWhenEmpty() = runBlocking {
        fakeSentimentApi.historyResponse = Response.success(
            SentimentHistoryResponseDto(
                symbol = "SYS",
                period = "1M",
                data = emptyList()
            )
        )

        val result = repository.getSentimentHistory("SYS", period = "1M", limit = 30)
        assertTrue(result.isSuccess)
        val history = result.getOrThrow()
        assertEquals(30, history.data.size)
        assertNotNull(history.data.first().date)
    }

    @Test
    fun testGetSentimentNewsFallbackWhenEmpty() = runBlocking {
        fakeSentimentApi.newsResponse = Response.success(
            SentimentNewsResponseDto(
                symbol = "OGDC",
                items = emptyList(),
                total = 0,
                page = 1,
                limit = 15
            )
        )

        fakeNewsApi.stockNewsResponse = Response.success(
            NewsListResponseDto(
                items = listOf(
                    NewsArticleResponseDto(
                        id = "ogdc_1",
                        title = "OGDC gas discovery",
                        sentiment = SentimentInfoDto("positive", 1.0, "finbert"),
                        publishedAt = "2026-09-25T10:00:00Z"
                    )
                )
            )
        )

        val result = repository.getSentimentNews("OGDC", page = 1, limit = 15, sentiment = null)
        assertTrue(result.isSuccess)
        val page = result.getOrThrow()
        assertEquals(1, page.items.size)
        assertEquals("OGDC gas discovery", page.items.first().title)
        assertEquals("BULLISH", page.items.first().sentiment)
    }

    // ─── Test Doubles ─────────────────────────────────────────────────────────

    class FakeSentimentApiService : SentimentApiService {
        var stockSentimentResponse: Response<SentimentResponseDto> = Response.error(
            404, "Not Found".toResponseBody("text/plain".toMediaType())
        )
        var historyResponse: Response<SentimentHistoryResponseDto> = Response.error(
            404, "Not Found".toResponseBody("text/plain".toMediaType())
        )
        var newsResponse: Response<SentimentNewsResponseDto> = Response.error(
            404, "Not Found".toResponseBody("text/plain".toMediaType())
        )
        var marketResponse: Response<MarketSentimentResponseDto> = Response.error(
            401, "Unauthorized".toResponseBody("text/plain".toMediaType())
        )

        override suspend fun getStockSentiment(symbol: String, days: Int?): Response<SentimentResponseDto> =
            stockSentimentResponse

        override suspend fun getSentimentHistory(symbol: String, period: String?, limit: Int?): Response<SentimentHistoryResponseDto> =
            historyResponse

        override suspend fun getSentimentNews(symbol: String, page: Int, limit: Int, sentiment: String?): Response<SentimentNewsResponseDto> =
            newsResponse

        override suspend fun getMarketSentiment(): Response<MarketSentimentResponseDto> =
            marketResponse
    }

    class FakeNewsApiService : NewsApiService {
        var stockNewsResponse: Response<NewsListResponseDto> = Response.success(NewsListResponseDto(emptyList()))
        var newsFeedResponse: Response<NewsListResponseDto> = Response.success(NewsListResponseDto(emptyList()))

        override suspend fun getStockNews(
            symbol: String,
            sentiment: String?,
            sourceType: String?,
            eventType: String?,
            limit: Int,
            cursor: String?
        ): Response<NewsListResponseDto> = stockNewsResponse

        override suspend fun getNewsFeed(
            row: String,
            symbol: String?,
            sentiment: String?,
            source: String?,
            sourceType: String?,
            eventType: String?,
            query: String?,
            limit: Int,
            cursor: String?
        ): Response<NewsListResponseDto> = newsFeedResponse

        override suspend fun refreshNews(force: Boolean?) = throw NotImplementedError()
        override suspend fun getRefreshStatus() = throw NotImplementedError()
        override suspend fun getMarketStatus() = throw NotImplementedError()
        override suspend fun getNewsSources() = throw NotImplementedError()
        override suspend fun getNewsArticle(articleId: String) = throw NotImplementedError()
        override suspend fun getEventsCalendar(fromDate: String?, toDate: String?, eventType: String?, symbol: String?) = throw NotImplementedError()
    }

    class FakeMarketApiService : MarketApiService {
        var sentimentOverviewResponse: Response<SentimentOverviewDto> = Response.success(
            SentimentOverviewDto("neutral", 100, 100, 50, 1.0, 50.0, 50.0, null, null)
        )

        override suspend fun getMarketSentimentOverview(): Response<SentimentOverviewDto> =
            sentimentOverviewResponse

        override suspend fun getMarketIndices() = TODO()
        override suspend fun getKse100Constituents() = TODO()
        override suspend fun getKse30Constituents() = TODO()
        override suspend fun getKmi30Constituents() = TODO()
        override suspend fun getTopGainers(limit: Int) = TODO()
        override suspend fun getTopLosers(limit: Int) = TODO()
        override suspend fun getVolumeSpikes(limit: Int) = TODO()
        override suspend fun getIndices() = TODO()
        override suspend fun getMarketOverview() = TODO()
        override suspend fun getSymbols(filter: String) = TODO()
        override suspend fun getMarketSentiment() = TODO()
        override suspend fun getSectorPerformances() = TODO()
    }
}
