package com.fyp.basarattradeinvest.domain.usecase.stocks

import com.fyp.basarattradeinvest.domain.model.stock.StockDetail
import com.fyp.basarattradeinvest.domain.repository.StockRepository

class GetStockOverviewUseCase(
    private val repository: StockRepository
) {
    suspend operator fun invoke(symbol: String): Result<StockDetail> {
        return repository.getStockOverview(symbol)
    }
}
