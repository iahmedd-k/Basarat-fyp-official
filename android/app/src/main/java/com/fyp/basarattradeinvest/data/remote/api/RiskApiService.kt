package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloResultResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.RiskVaRResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.StressTestResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface RiskApiService {

    @GET("api/v1/risk/var")
    suspend fun getValueAtRisk(
        @Query("confidence") confidence: Int? = null,
        @Query("horizon") horizon: String? = null
    ): Response<RiskVaRResponseDto>

    @POST("api/v1/risk/monte-carlo")
    suspend fun startMonteCarloSimulation(
        @Body request: MonteCarloRequestDto
    ): Response<MonteCarloResponseDto>

    @GET("api/v1/risk/monte-carlo/{task_id}")
    suspend fun getMonteCarloResult(
        @Path("task_id") taskId: String
    ): Response<MonteCarloResultResponseDto>

    @GET("api/v1/risk/stress-test")
    suspend fun getStressTest(
        @Query("scenario") scenario: String? = null
    ): Response<StressTestResponseDto>
}
