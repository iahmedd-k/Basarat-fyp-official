package com.fyp.basarattradeinvest.domain.model.portfolio

/**
 * Domain representations for Portfolio entities.
 * Kept clean from network annotations and JSON serialization details.
 */

data class PortfolioOverview(
    val summary: PortfolioSummary,
    val holdings: List<HoldingItem>,
    val updatedAt: String
)

data class PortfolioSummary(
    val totalInvested: Double,
    val currentValue: Double,
    val totalPnl: Double,
    val totalPnlPercent: Double,
    val todayPnl: Double
)

data class HoldingItem(
    val symbol: String,
    val quantity: Double,
    val averageCost: Double,
    val companyName: String,
    val sector: String,
    val currentPrice: Double?,
    val marketValue: Double?,
    val unrealizedPnl: Double?,
    val unrealizedPnlPercent: Double?,
    val portfolioWeight: Double?,
    val priceUpdatedAt: String?,
    val priceStatus: String
)

data class HoldingDetail(
    val symbol: String,
    val companyName: String,
    val sector: String,
    val quantity: Double,
    val averageCost: Double,
    val currentPrice: Double?,
    val investedValue: Double,
    val marketValue: Double?,
    val unrealizedPnl: Double?,
    val unrealizedPnlPercent: Double?,
    val realizedPnl: Double,
    val portfolioWeight: Double?,
    val transactions: List<PortfolioTransaction>,
    val priceUpdatedAt: String?,
    val priceStatus: String
)

data class PortfolioPnL(
    val realizedPnl: Double,
    val unrealizedPnl: Double,
    val totalPnl: Double,
    val totalPnlPercent: Double,
    val todayPnl: Double
)

data class PortfolioAllocation(
    val byStock: List<AllocationByStock>,
    val bySector: List<AllocationBySector>
)

data class AllocationByStock(
    val symbol: String,
    val marketValue: Double,
    val percentage: Double
)

data class AllocationBySector(
    val sector: String,
    val marketValue: Double,
    val percentage: Double
)

data class PortfolioPerformance(
    val period: String,
    val data: List<PerformancePoint>
)

data class PerformancePoint(
    val date: String,
    val value: Double
)

data class TransactionListPage(
    val items: List<PortfolioTransaction>,
    val total: Int,
    val page: Int,
    val limit: Int
)

data class PortfolioTransaction(
    val id: String,
    val symbol: String,
    val transactionType: String, // "BUY" or "SELL"
    val quantity: Double,
    val price: Double,
    val fee: Double,
    val transactionDate: String,
    val createdAt: String,
    val updatedAt: String
)

data class CompletedTrade(
    val symbol: String,
    val quantity: Double,
    val buyPrice: Double,
    val buyDate: String,
    val buyFee: Double,
    val sellPrice: Double,
    val sellDate: String,
    val sellFee: Double,
    val holdingPeriodDays: Int,
    val totalInvested: Double,
    val totalProceeds: Double,
    val realizedPnl: Double,
    val realizedPnlPercent: Double,
    val buyTransaction: PortfolioTransaction,
    val sellTransaction: PortfolioTransaction
)
