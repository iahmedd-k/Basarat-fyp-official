package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.portfolio.CompletedTrade
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingDetail
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPerformance
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPnL
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import com.fyp.basarattradeinvest.domain.model.portfolio.TransactionListPage

/**
 * Repository interface for all Portfolio data operations.
 */
interface PortfolioRepository {

    suspend fun getPortfolio(): Result<PortfolioOverview>

    suspend fun getHoldings(): Result<List<HoldingItem>>

    suspend fun getHoldingDetail(symbol: String): Result<HoldingDetail>

    suspend fun getPnL(): Result<PortfolioPnL>

    suspend fun getAllocation(): Result<PortfolioAllocation>

    suspend fun getPerformance(period: String = "1M"): Result<PortfolioPerformance>

    suspend fun getTransactions(
        page: Int = 1,
        limit: Int = 20,
        symbol: String? = null,
        transactionType: String? = null,
        fromDate: String? = null,
        toDate: String? = null
    ): Result<TransactionListPage>

    suspend fun getTransactionById(transactionId: String): Result<PortfolioTransaction>

    suspend fun createTransaction(
        symbol: String,
        type: String,
        quantity: Double,
        price: Double,
        fee: Double,
        date: String
    ): Result<PortfolioTransaction>

    suspend fun updateTransaction(
        transactionId: String,
        quantity: Double? = null,
        price: Double? = null,
        fee: Double? = null,
        date: String? = null
    ): Result<PortfolioTransaction>

    suspend fun deleteTransaction(transactionId: String): Result<Unit>

    suspend fun recordCompletedTrade(
        symbol: String,
        quantity: Double,
        buyPrice: Double,
        buyDate: String,
        buyFee: Double,
        sellPrice: Double,
        sellDate: String,
        sellFee: Double
    ): Result<CompletedTrade>
}
