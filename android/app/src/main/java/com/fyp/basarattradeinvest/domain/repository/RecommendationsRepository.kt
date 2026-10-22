package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationDetail
import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import com.fyp.basarattradeinvest.domain.model.recommendations.TargetStop

interface RecommendationsRepository {
    suspend fun getRecommendations(riskProfile: String? = "moderate", sector: String? = null, limit: Int = 20): Result<List<StockRecommendation>>
    /** Fetch only backend-provided candidates; never substitutes demo recommendations. */
    suspend fun getLiveRecommendations(
        riskProfile: String? = "moderate",
        sector: String? = null,
        limit: Int = 20
    ): Result<List<StockRecommendation>> = getRecommendations(riskProfile, sector, limit)
    suspend fun getRecommendationDetail(symbol: String, knownPrice: Double? = null): Result<RecommendationDetail>
    suspend fun getTargetStop(symbol: String, knownPrice: Double? = null): Result<TargetStop>
    /** Fetch backend target/stop values without the estimated fallback used by legacy screens. */
    suspend fun getLiveTargetStop(symbol: String): Result<TargetStop> = getTargetStop(symbol)
    suspend fun getEngineWeights(): Result<EngineWeights>
    suspend fun setEngineWeights(gruWeight: Double, technicalWeight: Double, fundamentalWeight: Double): Result<EngineWeights>
}
