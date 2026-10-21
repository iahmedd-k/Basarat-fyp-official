package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.domain.repository.MarketRepository

class GetMarketSentimentOverviewUseCase(
    private val repository: MarketRepository
) {
    suspend operator fun invoke(): Result<MarketSentiment> {
        return repository.getMarketSentimentOverview()
    }
}
