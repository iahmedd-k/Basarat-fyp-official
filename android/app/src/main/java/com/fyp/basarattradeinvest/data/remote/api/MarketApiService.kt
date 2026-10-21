package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.market.GainersResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.IndexConstituentsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.IndicesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.LosersResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.SentimentOverviewDto
import com.fyp.basarattradeinvest.data.remote.dto.market.VolumeSpikesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.MarketIndexDto
import com.fyp.basarattradeinvest.data.remote.dto.market.MarketOverviewDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.MarketSentimentDto
import com.fyp.basarattradeinvest.data.remote.dto.market.MarketStockDto
import com.fyp.basarattradeinvest.data.remote.dto.market.SectorPerformanceDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Query

interface MarketApiService {

    // --- Live BASARAT Swagger Endpoints (Source of Truth) ---

    @GET("api/v1/market/indices")
    suspend fun getMarketIndices(): Response<IndicesResponseDto>

    @GET("api/v1/market/indices/kse-100")
    suspend fun getKse100Constituents(): Response<IndexConstituentsResponseDto>

    @GET("api/v1/market/indices/kse-30")
    suspend fun getKse30Constituents(): Response<IndexConstituentsResponseDto>

    @GET("api/v1/market/indices/kmi-30")
    suspend fun getKmi30Constituents(): Response<IndexConstituentsResponseDto>

    @GET("api/v1/market/gainers")
    suspend fun getTopGainers(
        @Query("limit") limit: Int = 10
    ): Response<GainersResponseDto>

    @GET("api/v1/market/losers")
    suspend fun getTopLosers(
        @Query("limit") limit: Int = 10
    ): Response<LosersResponseDto>

    @GET("api/v1/market/volume-spikes")
    suspend fun getVolumeSpikes(
        @Query("limit") limit: Int = 10
    ): Response<VolumeSpikesResponseDto>

    @GET("api/v1/market/sentiment-overview")
    suspend fun getMarketSentimentOverview(): Response<SentimentOverviewDto>

    // --- Legacy / Compatibility Endpoints ---

    @GET("api/v1/markets/indices")
    suspend fun getIndices(): Response<List<MarketIndexDto>>

    @GET("api/v1/markets/overview")
    suspend fun getMarketOverview(): Response<MarketOverviewDto>

    @GET("api/v1/markets/symbols")
    suspend fun getSymbols(
        @Query("filter") filter: String
    ): Response<List<MarketStockDto>>

    @GET("api/v1/markets/sentiment")
    suspend fun getMarketSentiment(): Response<MarketSentimentDto>

    @GET("api/v1/market/sectors/performance")
    suspend fun getSectorPerformances(): Response<com.fyp.basarattradeinvest.data.remote.dto.market.SectorPerformanceListResponseDto>
}

