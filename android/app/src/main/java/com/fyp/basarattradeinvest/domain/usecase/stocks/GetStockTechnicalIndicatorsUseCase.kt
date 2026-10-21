package com.fyp.basarattradeinvest.domain.usecase.stocks

import com.fyp.basarattradeinvest.domain.model.stock.TechnicalAnalysis
import com.fyp.basarattradeinvest.domain.repository.StockRepository

class GetStockTechnicalIndicatorsUseCase(
    private val repository: StockRepository
) {
    suspend operator fun invoke(symbol: String): Result<TechnicalAnalysis> {
        return repository.getTechnicalIndicators(symbol)
    }
}
