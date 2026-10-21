package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.stocks.FundamentalsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.PriceHistoryResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.StockOverviewDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.StockSearchResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.TechnicalIndicatorsResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface StocksApiService {

    @GET("api/v1/stocks/search")
    suspend fun searchStocks(
        @Query("q") query: String,
        @Query("limit") limit: Int = 10
    ): Response<StockSearchResponseDto>

    @GET("api/v1/stocks/{symbol}/overview")
    suspend fun getStockOverview(
        @Path("symbol") symbol: String
    ): Response<StockOverviewDto>

    @GET("api/v1/stocks/{symbol}/price-history")
    suspend fun getPriceHistory(
        @Path("symbol") symbol: String,
        @Query("range") range: String = "1M"
    ): Response<PriceHistoryResponseDto>

    @GET("api/v1/stocks/{symbol}/technical-indicators")
    suspend fun getTechnicalIndicators(
        @Path("symbol") symbol: String,
        @Query("indicators") indicators: String = "RSI,MACD,BB,SMA,ADX",
        @Query("period") period: Int = 14,
        @Query("limit") limit: Int = 30
    ): Response<TechnicalIndicatorsResponseDto>

    @GET("api/v1/stocks/{symbol}/fundamentals")
    suspend fun getFundamentals(
        @Path("symbol") symbol: String
    ): Response<FundamentalsResponseDto>
}
