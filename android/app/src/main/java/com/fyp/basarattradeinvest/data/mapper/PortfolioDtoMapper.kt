package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.portfolio.AllocationBySectorDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.AllocationByStockDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.AllocationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.CompletedTradeResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.HoldingDetailResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.HoldingItemDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PerformancePointDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PerformanceResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PnLResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PortfolioResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.PortfolioSummaryDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionResponseDto
import com.fyp.basarattradeinvest.domain.model.portfolio.AllocationBySector
import com.fyp.basarattradeinvest.domain.model.portfolio.AllocationByStock
import com.fyp.basarattradeinvest.domain.model.portfolio.CompletedTrade
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingDetail
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import com.fyp.basarattradeinvest.domain.model.portfolio.PerformancePoint
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPerformance
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPnL
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioSummary
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import com.fyp.basarattradeinvest.domain.model.portfolio.TransactionListPage

/**
 * Mapper converting Portfolio DTOs to clean Domain models.
 */
object PortfolioDtoMapper {

    fun mapPortfolioResponse(dto: PortfolioResponseDto): PortfolioOverview {
        return PortfolioOverview(
            summary = mapSummary(dto.summary),
            holdings = dto.holdings.map { mapHoldingItem(it) },
            updatedAt = dto.updatedAt
        )
    }

    fun mapSummary(dto: PortfolioSummaryDto): PortfolioSummary {
        return PortfolioSummary(
            totalInvested = dto.totalInvested.toDoubleOrNull() ?: 0.0,
            currentValue = dto.currentValue.toDoubleOrNull() ?: 0.0,
            totalPnl = dto.totalPnl.toDoubleOrNull() ?: 0.0,
            totalPnlPercent = dto.totalPnlPercent,
            todayPnl = dto.todayPnl.toDoubleOrNull() ?: 0.0
        )
    }

    fun mapHoldingItem(dto: HoldingItemDto): HoldingItem {
        return HoldingItem(
            symbol = dto.symbol,
            quantity = dto.quantity.toDoubleOrNull() ?: 0.0,
            averageCost = dto.averageCost.toDoubleOrNull() ?: 0.0,
            companyName = dto.companyName ?: dto.symbol,
            sector = dto.sector ?: "General",
            currentPrice = dto.currentPrice?.toDoubleOrNull(),
            marketValue = dto.marketValue?.toDoubleOrNull(),
            unrealizedPnl = dto.unrealizedPnl?.toDoubleOrNull(),
            unrealizedPnlPercent = dto.unrealizedPnlPercent,
            portfolioWeight = dto.portfolioWeight,
            priceUpdatedAt = dto.priceUpdatedAt,
            priceStatus = dto.priceStatus ?: "AVAILABLE"
        )
    }

    fun mapHoldingDetail(dto: HoldingDetailResponseDto): HoldingDetail {
        return HoldingDetail(
            symbol = dto.symbol,
            companyName = dto.companyName ?: dto.symbol,
            sector = dto.sector ?: "General",
            quantity = dto.quantity.toDoubleOrNull() ?: 0.0,
            averageCost = dto.averageCost.toDoubleOrNull() ?: 0.0,
            currentPrice = dto.currentPrice?.toDoubleOrNull(),
            investedValue = dto.investedValue.toDoubleOrNull() ?: 0.0,
            marketValue = dto.marketValue?.toDoubleOrNull(),
            unrealizedPnl = dto.unrealizedPnl?.toDoubleOrNull(),
            unrealizedPnlPercent = dto.unrealizedPnlPercent,
            realizedPnl = dto.realizedPnl.toDoubleOrNull() ?: 0.0,
            portfolioWeight = dto.portfolioWeight,
            transactions = dto.transactions.map { mapTransaction(it) },
            priceUpdatedAt = dto.priceUpdatedAt,
            priceStatus = dto.priceStatus ?: "AVAILABLE"
        )
    }

    fun mapPnL(dto: PnLResponseDto): PortfolioPnL {
        return PortfolioPnL(
            realizedPnl = dto.realizedPnl.toDoubleOrNull() ?: 0.0,
            unrealizedPnl = dto.unrealizedPnl.toDoubleOrNull() ?: 0.0,
            totalPnl = dto.totalPnl.toDoubleOrNull() ?: 0.0,
            totalPnlPercent = dto.totalPnlPercent,
            todayPnl = dto.todayPnl.toDoubleOrNull() ?: 0.0
        )
    }

    fun mapAllocation(dto: AllocationResponseDto): PortfolioAllocation {
        return PortfolioAllocation(
            byStock = dto.byStock.map { mapAllocationStock(it) },
            bySector = dto.bySector.map { mapAllocationSector(it) }
        )
    }

    fun mapAllocationStock(dto: AllocationByStockDto): AllocationByStock {
        return AllocationByStock(
            symbol = dto.symbol,
            marketValue = dto.marketValue.toDoubleOrNull() ?: 0.0,
            percentage = dto.percentage
        )
    }

    fun mapAllocationSector(dto: AllocationBySectorDto): AllocationBySector {
        return AllocationBySector(
            sector = dto.sector,
            marketValue = dto.marketValue.toDoubleOrNull() ?: 0.0,
            percentage = dto.percentage
        )
    }

    fun mapPerformance(dto: PerformanceResponseDto): PortfolioPerformance {
        return PortfolioPerformance(
            period = dto.period,
            data = dto.data.map { mapPerformancePoint(it) }
        )
    }

    fun mapPerformancePoint(dto: PerformancePointDto): PerformancePoint {
        return PerformancePoint(
            date = dto.date,
            value = dto.value.toDoubleOrNull() ?: 0.0
        )
    }

    fun mapTransactionList(dto: TransactionListResponseDto): TransactionListPage {
        return TransactionListPage(
            items = dto.items.map { mapTransaction(it) },
            total = dto.total,
            page = dto.page,
            limit = dto.limit
        )
    }

    fun mapTransaction(dto: TransactionResponseDto): PortfolioTransaction {
        return PortfolioTransaction(
            id = dto.id,
            symbol = dto.symbol,
            transactionType = dto.transactionType,
            quantity = dto.quantity.toDoubleOrNull() ?: 0.0,
            price = dto.price.toDoubleOrNull() ?: 0.0,
            fee = dto.fee.toDoubleOrNull() ?: 0.0,
            transactionDate = dto.transactionDate,
            createdAt = dto.createdAt,
            updatedAt = dto.updatedAt
        )
    }

    fun mapCompletedTrade(dto: CompletedTradeResponseDto): CompletedTrade {
        return CompletedTrade(
            symbol = dto.symbol,
            quantity = dto.quantity.toDoubleOrNull() ?: 0.0,
            buyPrice = dto.buyPrice.toDoubleOrNull() ?: 0.0,
            buyDate = dto.buyDate,
            buyFee = dto.buyFee.toDoubleOrNull() ?: 0.0,
            sellPrice = dto.sellPrice.toDoubleOrNull() ?: 0.0,
            sellDate = dto.sellDate,
            sellFee = dto.sellFee.toDoubleOrNull() ?: 0.0,
            holdingPeriodDays = dto.holdingPeriodDays,
            totalInvested = dto.totalInvested.toDoubleOrNull() ?: 0.0,
            totalProceeds = dto.totalProceeds.toDoubleOrNull() ?: 0.0,
            realizedPnl = dto.realizedPnl.toDoubleOrNull() ?: 0.0,
            realizedPnlPercent = dto.realizedPnlPercent,
            buyTransaction = mapTransaction(dto.buyTransaction),
            sellTransaction = mapTransaction(dto.sellTransaction)
        )
    }
}
