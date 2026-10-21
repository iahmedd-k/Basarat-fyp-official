package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.MarketOverview
import com.fyp.basarattradeinvest.domain.repository.MarketRepository

class GetMarketOverviewUseCase(
    private val repository: MarketRepository
) {
    suspend operator fun invoke(): Result<MarketOverview> {
        return repository.getMarketOverview()
    }
}
