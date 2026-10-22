package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.portfolio.AllocationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.CompletedTradeCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.CompletedTradeResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.HoldingDetailResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.HoldingItemDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PerformanceResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PnLResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PortfolioResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionUpdateDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit interface for BASARAT Portfolio endpoints.
 * Source of truth: OpenAPI /api/v1/portfolio
 */
interface PortfolioApiService {

    @GET("api/v1/portfolio")
    suspend fun getPortfolio(): Response<PortfolioResponseDto>

    @GET("api/v1/portfolio/holdings")
    suspend fun getHoldings(): Response<List<HoldingItemDto>>

    @GET("api/v1/portfolio/holdings/{symbol}")
    suspend fun getHoldingDetail(
        @Path("symbol") symbol: String
    ): Response<HoldingDetailResponseDto>

    @GET("api/v1/portfolio/pnl")
    suspend fun getPnL(): Response<PnLResponseDto>

    @GET("api/v1/portfolio/allocation")
    suspend fun getAllocation(): Response<AllocationResponseDto>

    @GET("api/v1/portfolio/performance")
    suspend fun getPerformance(
        @Query("period") period: String = "1M"
    ): Response<PerformanceResponseDto>

    @GET("api/v1/portfolio/transactions")
    suspend fun getTransactions(
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
        @Query("symbol") symbol: String? = null,
        @Query("transaction_type") transactionType: String? = null,
        @Query("from_date") fromDate: String? = null,
        @Query("to_date") toDate: String? = null
    ): Response<TransactionListResponseDto>

    @POST("api/v1/portfolio/transactions")
    suspend fun createTransaction(
        @Body request: TransactionCreateDto
    ): Response<TransactionResponseDto>

    @GET("api/v1/portfolio/transactions/{transaction_id}")
    suspend fun getTransactionById(
        @Path("transaction_id") transactionId: String
    ): Response<TransactionResponseDto>

    @PATCH("api/v1/portfolio/transactions/{transaction_id}")
    suspend fun updateTransaction(
        @Path("transaction_id") transactionId: String,
        @Body request: TransactionUpdateDto
    ): Response<TransactionResponseDto>

    @DELETE("api/v1/portfolio/transactions/{transaction_id}")
    suspend fun deleteTransaction(
        @Path("transaction_id") transactionId: String
    ): Response<Unit>

    @POST("api/v1/portfolio/transactions/completed-trade")
    suspend fun recordCompletedTrade(
        @Body request: CompletedTradeCreateDto
    ): Response<CompletedTradeResponseDto>
}
