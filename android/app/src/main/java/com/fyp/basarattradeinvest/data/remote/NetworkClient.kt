package com.fyp.basarattradeinvest.data.remote

import com.fyp.basarattradeinvest.core.network.AuthInterceptor
import com.fyp.basarattradeinvest.core.network.TokenAuthenticator
import com.fyp.basarattradeinvest.data.remote.api.AuthApiService
import com.fyp.basarattradeinvest.data.remote.api.LiveMarketApiService
import com.fyp.basarattradeinvest.data.remote.api.MarketApiService
import com.fyp.basarattradeinvest.data.remote.live.LiveMarketDataSource
import com.fyp.basarattradeinvest.data.repository.LiveMarketRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.LiveMarketRepository
import okhttp3.Dispatcher
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object NetworkClient {

    // Live backend host (AWS EC2 FastAPI backend, fronted by the domain)
    const val BASE_URL = "https://api.basarat.live/"

    // Live PSX Market API host (Real-time Market quotes, gainers, losers, volume spikes, indices, sectors)
    const val MARKET_BASE_URL = "https://api.basarat.live/"

    // Sanitized logging interceptor: redacts sensitive Authorization headers & tokens.
    // BASIC (method/url/code/duration) avoids buffering every full response body, which
    // Level.BODY does and which adds latency to each call over the slow market backend.
    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BASIC
        redactHeader("Authorization")
        redactHeader("Cookie")
        redactHeader("Set-Cookie")
    }

    // BODY logging reads the complete response body before returning it, which defeats SSE
    // streaming. Keep stream logging to headers and allow more idle time for model generation.
    private val streamingLoggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.HEADERS
        redactHeader("Authorization")
        redactHeader("Cookie")
        redactHeader("Set-Cookie")
    }

    // Device registration bodies contain the FCM token. Keep these requests out of BODY logs.
    private val headersOnlyLoggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.HEADERS
        redactHeader("Authorization")
        redactHeader("Cookie")
        redactHeader("Set-Cookie")
    }

    private val streamAwareLoggingInterceptor = Interceptor { chain ->
        val request = chain.request()
        if (request.url.encodedPath.startsWith("/api/v1/devices/")) {
            headersOnlyLoggingInterceptor.intercept(chain)
        } else if (request.url.encodedPath == "/api/v1/assistant/chat/stream") {
            streamingLoggingInterceptor.intercept(chain.withReadTimeout(2, TimeUnit.MINUTES))
        } else {
            loggingInterceptor.intercept(chain)
        }
    }

    private val authInterceptor = AuthInterceptor()
    private val tokenAuthenticator = TokenAuthenticator(BASE_URL)

    // Every screen talks to the same host, so OkHttp's default of 5 concurrent requests per host
    // made a screen's own fan-out (Portfolio fires 5) queue behind Home/Market/notification calls.
    private val dispatcher = Dispatcher().apply {
        maxRequestsPerHost = 12
    }

    private val okHttpClient = OkHttpClient.Builder()
        .dispatcher(dispatcher)
        .addInterceptor(authInterceptor)
        .addInterceptor(streamAwareLoggingInterceptor)
        .authenticator(tokenAuthenticator)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    private val marketRetrofit = Retrofit.Builder()
        .baseUrl(MARKET_BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val marketApiService: MarketApiService by lazy {
        marketRetrofit.create(MarketApiService::class.java)
    }

    val liveMarketApiService: LiveMarketApiService by lazy {
        marketRetrofit.create(LiveMarketApiService::class.java)
    }

    /** Singleton WebSocket data source shared across all screens. */
    val liveMarketDataSource: LiveMarketDataSource by lazy {
        LiveMarketDataSource(
            okHttpClient = okHttpClient.newBuilder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .build(),
            liveMarketApiService = liveMarketApiService
        )
    }

    /** Singleton repository that wraps [liveMarketDataSource]; shared across all ViewModels. */
    val liveMarketRepository: LiveMarketRepository by lazy {
        LiveMarketRepositoryImpl(liveMarketDataSource)
    }

    val authApiService: AuthApiService by lazy {
        retrofit.create(AuthApiService::class.java)
    }

    val usersApiService: com.fyp.basarattradeinvest.data.remote.api.UsersApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.UsersApiService::class.java)
    }

    val forecastApiService: com.fyp.basarattradeinvest.data.remote.api.ForecastApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.ForecastApiService::class.java)
    }

    val stocksApiService: com.fyp.basarattradeinvest.data.remote.api.StocksApiService by lazy {
        marketRetrofit.create(com.fyp.basarattradeinvest.data.remote.api.StocksApiService::class.java)
    }

    val recommendationsApiService: com.fyp.basarattradeinvest.data.remote.api.RecommendationsApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.RecommendationsApiService::class.java)
    }

    val portfolioApiService: com.fyp.basarattradeinvest.data.remote.api.PortfolioApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.PortfolioApiService::class.java)
    }

    val riskApiService: com.fyp.basarattradeinvest.data.remote.api.RiskApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.RiskApiService::class.java)
    }

    val sentimentApiService: com.fyp.basarattradeinvest.data.remote.api.SentimentApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.SentimentApiService::class.java)
    }

    val newsApiService: com.fyp.basarattradeinvest.data.remote.api.NewsApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.NewsApiService::class.java)
    }

    val alertsApiService: com.fyp.basarattradeinvest.data.remote.api.AlertsApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.AlertsApiService::class.java)
    }

    val watchlistApiService: com.fyp.basarattradeinvest.data.remote.api.WatchlistApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.WatchlistApiService::class.java)
    }

    val watchlistRepository: com.fyp.basarattradeinvest.domain.repository.WatchlistRepository by lazy {
        com.fyp.basarattradeinvest.data.repository.WatchlistRepositoryImpl(watchlistApiService)
    }

    val notificationsApiService: com.fyp.basarattradeinvest.data.remote.api.NotificationsApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.NotificationsApiService::class.java)
    }

    val devicesApiService: com.fyp.basarattradeinvest.data.remote.api.DevicesApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.DevicesApiService::class.java)
    }

    val shariahApiService: com.fyp.basarattradeinvest.data.remote.api.ShariahApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.ShariahApiService::class.java)
    }

    val communityApiService: com.fyp.basarattradeinvest.data.remote.api.CommunityApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.CommunityApiService::class.java)
    }

    val assistantApiService: com.fyp.basarattradeinvest.data.remote.api.AssistantApiService by lazy {
        retrofit.create(com.fyp.basarattradeinvest.data.remote.api.AssistantApiService::class.java)
    }

    val ipoApiService: com.fyp.basarattradeinvest.data.remote.api.IpoApiService by lazy {
        marketRetrofit.create(com.fyp.basarattradeinvest.data.remote.api.IpoApiService::class.java)
    }

    val etfApiService: com.fyp.basarattradeinvest.data.remote.api.EtfApiService by lazy {
        marketRetrofit.create(com.fyp.basarattradeinvest.data.remote.api.EtfApiService::class.java)
    }

    val ipoRepository: com.fyp.basarattradeinvest.domain.repository.IpoRepository by lazy {
        com.fyp.basarattradeinvest.data.repository.IpoRepositoryImpl(ipoApiService)
    }

    val etfRepository: com.fyp.basarattradeinvest.domain.repository.EtfRepository by lazy {
        com.fyp.basarattradeinvest.data.repository.EtfRepositoryImpl(etfApiService)
    }
}
