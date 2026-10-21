package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.IndexConstituents
import com.fyp.basarattradeinvest.domain.repository.MarketRepository

class GetKmi30ConstituentsUseCase(
    private val repository: MarketRepository
) {
    suspend operator fun invoke(): Result<IndexConstituents> {
        return repository.getKmi30Constituents()
    }
}
