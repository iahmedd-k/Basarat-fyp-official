package com.fyp.basarattradeinvest.domain.usecase.recommendations

import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository

class SetEngineWeightsUseCase(
    private val repository: RecommendationsRepository
) {
    suspend operator fun invoke(
        gruWeight: Double,
        technicalWeight: Double,
        fundamentalWeight: Double
    ): Result<EngineWeights> {
        return repository.setEngineWeights(gruWeight, technicalWeight, fundamentalWeight)
    }
}
