package com.fyp.basarattradeinvest.domain.usecase.recommendations

import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository

class GetEngineWeightsUseCase(
    private val repository: RecommendationsRepository
) {
    suspend operator fun invoke(): Result<EngineWeights> {
        return repository.getEngineWeights()
    }
}
