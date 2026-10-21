package com.fyp.basarattradeinvest.domain.usecase.recommendations

import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository

class GetRecommendationsUseCase(
    private val repository: RecommendationsRepository
) {
    suspend operator fun invoke(
        riskProfile: String? = "moderate",
        sector: String? = null,
        limit: Int = 20
    ): Result<List<StockRecommendation>> {
        return repository.getRecommendations(riskProfile, sector, limit)
    }
}
