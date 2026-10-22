package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.live.RestQuotesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahCriteriaResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahKmi30ResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahPurificationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahScreeningResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit service definition for BASARAT Shariah module.
 * Source of truth: OpenAPI at <base url>/api/v1/openapi.json (see NetworkClient for the host).
 */
interface ShariahApiService {

    @GET("api/v1/shariah/kmi30")
    suspend fun getKmi30Constituents(): Response<ShariahKmi30ResponseDto>

    /**
     * The full PSX board. The Shariah module only has a bulk compliance list for KMI-30, so
     * every other symbol is screened one at a time via [getShariahScreening] when the user
     * opens it; this endpoint supplies the universe to pick from.
     */
    @GET("api/v1/market/all-stocks")
    suspend fun getAllStocks(
        @Query("limit") limit: Int = 1000,
        @Query("offset") offset: Int = 0,
        @Query("sort_by") sortBy: String = "symbol",
        @Query("order") order: String = "asc"
    ): Response<RestQuotesResponseDto>

    @GET("api/v1/shariah/{symbol}")
    suspend fun getShariahScreening(
        @Path("symbol") symbol: String
    ): Response<ShariahScreeningResponseDto>

    @GET("api/v1/shariah/{symbol}/criteria")
    suspend fun getShariahCriteria(
        @Path("symbol") symbol: String
    ): Response<ShariahCriteriaResponseDto>

    @GET("api/v1/shariah/{symbol}/purification")
    suspend fun getShariahPurification(
        @Path("symbol") symbol: String,
        @Query("dividend_income") dividendIncome: Double
    ): Response<ShariahPurificationResponseDto>
}
