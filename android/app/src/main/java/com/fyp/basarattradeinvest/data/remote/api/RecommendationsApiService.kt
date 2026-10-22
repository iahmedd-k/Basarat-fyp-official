package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.recommendations.EngineWeightsRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.recommendations.EngineWeightsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.recommendations.RecommendationDetailResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.recommendations.RecommendationsListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.recommendations.TargetStopResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface RecommendationsApiService {

    @GET("api/v1/recommendations")
    suspend fun getRecommendations(
        @Query("risk_profile") riskProfile: String? = "moderate",
        @Query("sector") sector: String? = null,
        @Query("limit") limit: Int = 20
    ): Response<RecommendationsListResponseDto>

    @GET("api/v1/recommendations/engine-weights")
    suspend fun getEngineWeights(): Response<EngineWeightsResponseDto>

    @POST("api/v1/recommendations/engine-weights")
    suspend fun setEngineWeights(
        @Body request: EngineWeightsRequestDto
    ): Response<EngineWeightsResponseDto>

    @GET("api/v1/recommendations/{symbol}")
    suspend fun getRecommendationDetail(
        @Path("symbol") symbol: String
    ): Response<RecommendationDetailResponseDto>

    @GET("api/v1/recommendations/{symbol}/target-stop")
    suspend fun getTargetStop(
        @Path("symbol") symbol: String
    ): Response<TargetStopResponseDto>
}
