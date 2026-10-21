package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.repository.MarketRepository

class GetMarketIndicesUseCase(
    private val repository: MarketRepository
) {
    suspend operator fun invoke(): Result<List<MarketIndex>> {
        return repository.getMarketIndices()
    }
}
