package com.fyp.basarattradeinvest.domain.usecase.stocks

import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.repository.StockRepository

class GetStockPriceHistoryUseCase(
    private val repository: StockRepository
) {
    suspend operator fun invoke(symbol: String, range: String = "1M"): Result<List<CandleEntry>> {
        return repository.getPriceHistory(symbol, range)
    }
}
