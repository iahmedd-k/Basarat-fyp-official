package com.fyp.basarattradeinvest.domain.usecase.forecast

import com.fyp.basarattradeinvest.domain.model.stock.StockForecast
import com.fyp.basarattradeinvest.domain.repository.ForecastRepository

/**
 * UseCase to fetch current ML forecast for a stock
 */
class GetStockForecastUseCase(
    private val repository: ForecastRepository
) {
    suspend operator fun invoke(symbol: String, horizon: String = "1W"): Result<StockForecast> {
        if (symbol.isBlank()) {
            return Result.failure(IllegalArgumentException("Stock symbol cannot be blank"))
        }
        return repository.getStockForecast(symbol.trim().uppercase(), horizon)
    }
}
