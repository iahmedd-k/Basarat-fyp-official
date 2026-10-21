package com.fyp.basarattradeinvest.domain.usecase.shariah

import com.fyp.basarattradeinvest.domain.model.shariah.ShariahStock
import com.fyp.basarattradeinvest.domain.repository.ShariahRepository

class GetShariahStocksUseCase(
    private val repository: ShariahRepository
) {
    suspend operator fun invoke(
        category: String = "All Stocks",
        query: String? = null
    ): Result<List<ShariahStock>> {
        return repository.getShariahCompliantStocks(category, query)
    }
}
