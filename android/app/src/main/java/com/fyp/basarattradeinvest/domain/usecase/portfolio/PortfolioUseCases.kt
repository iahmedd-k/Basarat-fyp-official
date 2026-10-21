package com.fyp.basarattradeinvest.domain.usecase.portfolio

import com.fyp.basarattradeinvest.domain.model.portfolio.CompletedTrade
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingDetail
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPerformance
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPnL
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import com.fyp.basarattradeinvest.domain.model.portfolio.TransactionListPage
import com.fyp.basarattradeinvest.domain.repository.PortfolioRepository

class GetPortfolioOverviewUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(): Result<PortfolioOverview> = repository.getPortfolio()
}

class GetHoldingsUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(): Result<List<HoldingItem>> = repository.getHoldings()
}

class GetHoldingDetailUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(symbol: String): Result<HoldingDetail> = repository.getHoldingDetail(symbol)
}

class GetPortfolioPnLUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(): Result<PortfolioPnL> = repository.getPnL()
}

class GetPortfolioAllocationUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(): Result<PortfolioAllocation> = repository.getAllocation()
}

class GetPortfolioPerformanceUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(period: String = "1M"): Result<PortfolioPerformance> = repository.getPerformance(period)
}

class GetTransactionsUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(
        page: Int = 1,
        limit: Int = 20,
        symbol: String? = null,
        transactionType: String? = null,
        fromDate: String? = null,
        toDate: String? = null
    ): Result<TransactionListPage> = repository.getTransactions(page, limit, symbol, transactionType, fromDate, toDate)
}

class GetTransactionDetailUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(transactionId: String): Result<PortfolioTransaction> = repository.getTransactionById(transactionId)
}

class CreateTransactionUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(
        symbol: String,
        type: String,
        quantity: Double,
        price: Double,
        fee: Double,
        date: String
    ): Result<PortfolioTransaction> = repository.createTransaction(symbol, type, quantity, price, fee, date)
}

class UpdateTransactionUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(
        transactionId: String,
        quantity: Double? = null,
        price: Double? = null,
        fee: Double? = null,
        date: String? = null
    ): Result<PortfolioTransaction> = repository.updateTransaction(transactionId, quantity, price, fee, date)
}

class DeleteTransactionUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(transactionId: String): Result<Unit> = repository.deleteTransaction(transactionId)
}

class RecordCompletedTradeUseCase(
    private val repository: PortfolioRepository
) {
    suspend operator fun invoke(
        symbol: String,
        quantity: Double,
        buyPrice: Double,
        buyDate: String,
        buyFee: Double,
        sellPrice: Double,
        sellDate: String,
        sellFee: Double
    ): Result<CompletedTrade> = repository.recordCompletedTrade(symbol, quantity, buyPrice, buyDate, buyFee, sellPrice, sellDate, sellFee)
}
