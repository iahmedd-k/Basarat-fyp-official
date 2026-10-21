package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.SectorPerformance
import com.fyp.basarattradeinvest.domain.repository.MarketRepository

class GetSectorPerformancesUseCase(
    private val repository: MarketRepository
) {
    suspend operator fun invoke(): Result<List<SectorPerformance>> {
        return repository.getSectorPerformances()
    }
}
