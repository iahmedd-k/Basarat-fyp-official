package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.market.IndexConstituents
import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.market.MarketOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.model.market.SectorPerformance
import com.fyp.basarattradeinvest.domain.model.stock.SymbolFilterType

interface MarketRepository {
    // --- Live BASARAT Endpoints ---
    suspend fun getMarketIndices(): Result<List<MarketIndex>>
    suspend fun getKse100Constituents(): Result<IndexConstituents>
    suspend fun getKse30Constituents(): Result<IndexConstituents>
    suspend fun getKmi30Constituents(): Result<IndexConstituents>
    suspend fun getTopGainers(limit: Int = 10): Result<List<MarketStock>>
    suspend fun getTopLosers(limit: Int = 10): Result<List<MarketStock>>
    suspend fun getVolumeSpikes(limit: Int = 10): Result<List<MarketStock>>
    suspend fun getMarketSentimentOverview(): Result<MarketSentiment>

    // --- Compatibility Methods ---
    suspend fun getMarketOverview(): Result<MarketOverview>
    suspend fun getTopSymbols(filterType: SymbolFilterType): Result<List<MarketStock>>
    suspend fun getMarketSentiment(): Result<MarketSentiment>
    suspend fun getSectorPerformances(): Result<List<SectorPerformance>>
}

