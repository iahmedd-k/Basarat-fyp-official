package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.repository.MarketRepository

class GetVolumeSpikesUseCase(
    private val repository: MarketRepository
) {
    suspend operator fun invoke(limit: Int = 10): Result<List<MarketStock>> {
        return repository.getVolumeSpikes(limit)
    }
}
