package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.forecast.ForecastHistoryResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.forecast.ForecastResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit interface for BASARAT ML Forecast API endpoints
 */
interface ForecastApiService {

    /**
     * GET /api/v1/forecast/{symbol}
     * Get ML forecast for a stock
     * @param symbol PSX stock symbol
     * @param horizon Forecast horizon ("1D", "1W", "2W", "1M")
     */
    @GET("api/v1/forecast/{symbol}")
    suspend fun getStockForecast(
        @Path("symbol") symbol: String,
        @Query("horizon") horizon: String? = "1W"
    ): Response<ForecastResponseDto>

    /**
     * GET /api/v1/forecast/{symbol}/history
     * Get historical forecast accuracy and predictions
     * @param symbol PSX stock symbol
     * @param horizon History horizon filter ("1D", "1W", "2W", "1M")
     * @param limit Maximum historical predictions (1-100, default 30)
     */
    @GET("api/v1/forecast/{symbol}/history")
    suspend fun getForecastHistory(
        @Path("symbol") symbol: String,
        @Query("horizon") horizon: String? = "1W",
        @Query("limit") limit: Int? = 30
    ): Response<ForecastHistoryResponseDto>
}
