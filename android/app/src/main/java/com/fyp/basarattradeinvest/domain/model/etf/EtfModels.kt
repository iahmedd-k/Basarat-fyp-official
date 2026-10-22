package com.fyp.basarattradeinvest.domain.model.etf

import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfHistoryEntryDto
import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfItemDto
import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfPerformanceDto
import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfQuoteDto
import com.fyp.basarattradeinvest.data.remote.dto.etf.EtfReturnsDto

data class EtfQuote(
    val currentPrice: Double?,
    val change: Double?,
    val changePercent: Double?,
    val openPrice: Double?,
    val highPrice: Double?,
    val lowPrice: Double?,
    val closePrice: Double?,
    val volume: Long?,
    val bidPrice: Double?,
    val askPrice: Double?,
    val dataAsOf: String?,
    val quoteSource: String?
)

fun EtfQuoteDto.toDomain(): EtfQuote = EtfQuote(
    currentPrice = currentPrice,
    change = change,
    changePercent = changePercent,
    openPrice = openPrice,
    highPrice = highPrice,
    lowPrice = lowPrice,
    closePrice = closePrice,
    volume = volume,
    bidPrice = bidPrice,
    askPrice = askPrice,
    dataAsOf = dataAsOf,
    quoteSource = quoteSource
)

data class EtfItem(
    val id: String?,
    val symbol: String,
    val name: String,
    val fundManager: String?,
    val category: String?,
    val benchmarkIndex: String?,
    val isShariahCompliant: Boolean,
    val expenseRatio: Double?,
    val inceptionDate: String?,
    val totalAssetsPkr: Double?,
    val description: String?,
    val isActive: Boolean,
    val quote: EtfQuote?,
    val currentPrice: Double?,
    val change: Double?,
    val changePercent: Double?,
    val volume: Long?,
    val createdAt: String?,
    val updatedAt: String?
)

fun EtfItemDto.toDomain(): EtfItem = EtfItem(
    id = id,
    symbol = symbol ?: "",
    name = name ?: symbol ?: "",
    fundManager = fundManager,
    category = category,
    benchmarkIndex = benchmarkIndex,
    isShariahCompliant = isShariahCompliant ?: false,
    expenseRatio = expenseRatio,
    inceptionDate = inceptionDate,
    totalAssetsPkr = totalAssetsPkr,
    description = description,
    isActive = isActive ?: true,
    quote = quote?.toDomain(),
    currentPrice = currentPrice ?: quote?.currentPrice,
    change = change ?: quote?.change,
    changePercent = changePercent ?: quote?.changePercent,
    volume = volume ?: quote?.volume,
    createdAt = createdAt,
    updatedAt = updatedAt
)

data class EtfsResult(
    val total: Int,
    val shariahCount: Int,
    val conventionalCount: Int,
    val etfs: List<EtfItem>
)

data class EtfHistoryEntry(
    val date: String,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Long
)

fun EtfHistoryEntryDto.toDomain(): EtfHistoryEntry = EtfHistoryEntry(
    date = date ?: "",
    open = open ?: 0.0,
    high = high ?: 0.0,
    low = low ?: 0.0,
    close = close ?: 0.0,
    volume = volume ?: 0L
)

data class EtfReturns(
    val oneDay: Double?,
    val oneWeek: Double?,
    val oneMonth: Double?,
    val threeMonths: Double?,
    val oneYear: Double?,
    val ytd: Double?
)

fun EtfReturnsDto.toDomain(): EtfReturns = EtfReturns(
    oneDay = oneDay,
    oneWeek = oneWeek,
    oneMonth = oneMonth,
    threeMonths = threeMonths,
    oneYear = oneYear,
    ytd = ytd
)

data class EtfPerformance(
    val symbol: String,
    val name: String?,
    val benchmarkIndex: String?,
    val returns: EtfReturns?,
    val benchmarkReturns: EtfReturns?,
    val trackingDifference1m: Double?,
    val volatilityAnnualized: Double?
)

fun EtfPerformanceDto.toDomain(): EtfPerformance = EtfPerformance(
    symbol = symbol ?: "",
    name = name,
    benchmarkIndex = benchmarkIndex,
    returns = returns?.toDomain(),
    benchmarkReturns = benchmarkReturns?.toDomain(),
    trackingDifference1m = trackingDifference1m,
    volatilityAnnualized = volatilityAnnualized
)
