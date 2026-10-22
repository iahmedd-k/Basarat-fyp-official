package com.fyp.basarattradeinvest.domain.usecase.recommendations

import com.fyp.basarattradeinvest.domain.model.recommendations.TargetStop
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository

class GetTargetStopUseCase(
    private val repository: RecommendationsRepository
) {
    suspend operator fun invoke(symbol: String, knownPrice: Double? = null): Result<TargetStop> {
        return repository.getTargetStop(symbol, knownPrice)
    }
}
