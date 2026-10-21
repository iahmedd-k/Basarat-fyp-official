package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.ipo.IpoCalendarResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.ipo.IpoItemDto
import com.fyp.basarattradeinvest.data.remote.dto.ipo.IpoPerformanceResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.ipo.IposResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit interface for BASARAT PSX IPO endpoints (public).
 */
interface IpoApiService {

    @GET("api/v1/ipos")
    suspend fun getIpos(
        @Query("status") status: String? = null,
        @Query("sector") sector: String? = null,
        @Query("is_shariah_compliant") isShariahCompliant: Boolean? = null,
        @Query("search") search: String? = null,
        @Query("limit") limit: Int = 50,
        @Query("offset") offset: Int = 0
    ): Response<IposResponseDto>

    @GET("api/v1/ipos/calendar")
    suspend fun getIpoCalendar(): Response<IpoCalendarResponseDto>

    @GET("api/v1/ipos/performance")
    suspend fun getIpoPerformance(): Response<IpoPerformanceResponseDto>

    @GET("api/v1/ipos/{symbol}")
    suspend fun getIpoDetail(@Path("symbol") symbol: String): Response<IpoItemDto>
}
