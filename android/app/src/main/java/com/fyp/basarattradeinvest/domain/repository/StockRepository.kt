package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.FundamentalMetrics
import com.fyp.basarattradeinvest.domain.model.stock.StockAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.StockDetail
import com.fyp.basarattradeinvest.domain.model.stock.StockTrade

interface StockRepository {
    suspend fun getStockDetail(symbol: String): Result<StockDetail>
    suspend fun getChartData(symbol: String, timeframe: String): Result<List<CandleEntry>>
    suspend fun getRecentTrades(symbol: String): Result<List<StockTrade>>
    suspend fun getStockAnalysis(symbol: String): Result<StockAnalysis>

    // New backend-backed stock methods
    suspend fun searchStocks(query: String, limit: Int = 10): Result<List<com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult>>
    suspend fun getStockOverview(symbol: String): Result<StockDetail>
    suspend fun getPriceHistory(symbol: String, range: String = "1M"): Result<List<CandleEntry>>
    suspend fun getTechnicalIndicators(symbol: String): Result<com.fyp.basarattradeinvest.domain.model.stock.TechnicalAnalysis>
    suspend fun getFundamentals(symbol: String): Result<com.fyp.basarattradeinvest.domain.model.stock.FundamentalMetrics>
}
