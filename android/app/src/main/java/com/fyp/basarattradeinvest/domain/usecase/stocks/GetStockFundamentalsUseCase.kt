package com.fyp.basarattradeinvest.domain.usecase.stocks

import com.fyp.basarattradeinvest.domain.model.stock.FundamentalMetrics
import com.fyp.basarattradeinvest.domain.repository.StockRepository

class GetStockFundamentalsUseCase(
    private val repository: StockRepository
) {
    suspend operator fun invoke(symbol: String): Result<FundamentalMetrics> {
        return repository.getFundamentals(symbol)
    }
}
