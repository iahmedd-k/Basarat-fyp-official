package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.shariah.ShariahStock
import com.fyp.basarattradeinvest.domain.model.shariah.DividendPurificationResult
import com.fyp.basarattradeinvest.domain.model.shariah.Kmi30IndexSummary
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCompliance
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCriteria

interface ShariahRepository {

    suspend fun getKmi30Constituents(): Result<Kmi30IndexSummary>

    suspend fun getStockShariahScreening(symbol: String): Result<StockShariahCompliance>

    suspend fun getStockShariahCriteria(symbol: String): Result<StockShariahCriteria>

    suspend fun calculatePurification(
        symbol: String,
        dividendIncome: Double
    ): Result<DividendPurificationResult>

    suspend fun getShariahCompliantStocks(
        category: String = "All Stocks",
        query: String? = null
    ): Result<List<ShariahStock>>
}
