package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfHistoryResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfItemDto
import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfPerformanceDto
import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfsResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit interface for BASARAT PSX ETF endpoints (public).
 */
interface EtfApiService {

    @GET("api/v1/etfs")
    suspend fun getEtfs(
        @Query("category") category: String? = null,
        @Query("is_shariah_compliant") isShariahCompliant: Boolean? = null,
        @Query("search") search: String? = null
    ): Response<EtfsResponseDto>

    @GET("api/v1/etfs/{symbol}")
    suspend fun getEtfDetail(@Path("symbol") symbol: String): Response<EtfItemDto>

    @GET("api/v1/etfs/{symbol}/history")
    suspend fun getEtfHistory(
        @Path("symbol") symbol: String,
        @Query("timeframe") timeframe: String = "1M"
    ): Response<EtfHistoryResponseDto>

    @GET("api/v1/etfs/{symbol}/performance")
    suspend fun getEtfPerformance(@Path("symbol") symbol: String): Response<EtfPerformanceDto>
}
