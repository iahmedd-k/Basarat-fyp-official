package com.fyp.basarattradeinvest.domain.usecase.shariah

import com.fyp.basarattradeinvest.domain.model.shariah.DividendPurificationResult
import com.fyp.basarattradeinvest.domain.model.shariah.Kmi30IndexSummary
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCompliance
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCriteria
import com.fyp.basarattradeinvest.domain.repository.ShariahRepository

class GetKmi30ConstituentsUseCase(
    private val repository: ShariahRepository
) {
    suspend operator fun invoke(): Result<Kmi30IndexSummary> {
        return repository.getKmi30Constituents()
    }
}

class GetStockShariahScreeningUseCase(
    private val repository: ShariahRepository
) {
    suspend operator fun invoke(symbol: String): Result<StockShariahCompliance> {
        return repository.getStockShariahScreening(symbol)
    }
}

class GetStockShariahCriteriaUseCase(
    private val repository: ShariahRepository
) {
    suspend operator fun invoke(symbol: String): Result<StockShariahCriteria> {
        return repository.getStockShariahCriteria(symbol)
    }
}

class CalculateDividendPurificationUseCase(
    private val repository: ShariahRepository
) {
    suspend operator fun invoke(
        symbol: String,
        dividendIncome: Double
    ): Result<DividendPurificationResult> {
        require(dividendIncome > 0.0) { "Dividend income must be greater than zero." }
        return repository.calculatePurification(symbol, dividendIncome)
    }
}
