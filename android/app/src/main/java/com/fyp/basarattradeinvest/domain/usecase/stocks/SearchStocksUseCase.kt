package com.fyp.basarattradeinvest.domain.usecase.stocks

import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult
import com.fyp.basarattradeinvest.domain.repository.StockRepository

class SearchStocksUseCase(
    private val repository: StockRepository
) {
    suspend operator fun invoke(query: String, limit: Int = 10): Result<List<StockSearchResult>> {
        if (query.trim().isEmpty()) {
            return Result.success(emptyList())
        }
        return repository.searchStocks(query.trim(), limit)
    }
}
