package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.model.stock.SymbolFilterType
import com.fyp.basarattradeinvest.domain.repository.MarketRepository

class GetTopSymbolsUseCase(
    private val repository: MarketRepository
) {
    suspend operator fun invoke(filterType: SymbolFilterType): Result<List<MarketStock>> {
        return repository.getTopSymbols(filterType)
    }
}
