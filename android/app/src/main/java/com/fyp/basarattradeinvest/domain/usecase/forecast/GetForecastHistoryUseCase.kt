package com.fyp.basarattradeinvest.domain.usecase.forecast

import com.fyp.basarattradeinvest.domain.model.stock.ForecastHistory
import com.fyp.basarattradeinvest.domain.repository.ForecastRepository

/**
 * UseCase to fetch historical forecast performance and accuracy
 */
class GetForecastHistoryUseCase(
    private val repository: ForecastRepository
) {
    suspend operator fun invoke(symbol: String, horizon: String = "1W", limit: Int = 30): Result<ForecastHistory> {
        if (symbol.isBlank()) {
            return Result.failure(IllegalArgumentException("Stock symbol cannot be blank"))
        }
        val safeLimit = limit.coerceIn(1, 100)
        val safeHorizon = horizon.uppercase().takeIf { it in setOf("1D", "1W", "2W", "1M") }
            ?: return Result.failure(IllegalArgumentException("Unsupported forecast horizon: $horizon"))
        return repository.getForecastHistory(symbol.trim().uppercase(), safeHorizon, safeLimit)
    }
}
