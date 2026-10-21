package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.BenchmarkTrend
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.market.IndexConstituents
import com.fyp.basarattradeinvest.domain.repository.MarketRepository
import com.fyp.basarattradeinvest.domain.repository.StockRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.sync.withPermit

/**
 * Builds the Home benchmark trend for a timeframe from the index' own constituents.
 *
 * One fetch of each constituent's full 1Y history feeds every pill, which then slices dates
 * locally instead of re-querying the backend per range. The result is a labelled equal-weight
 * proxy, never an official index level.
 */
class BuildBenchmarkTrendUseCase(
    private val marketRepository: MarketRepository,
    private val stockRepository: StockRepository
) {

    private val historyMutex = Mutex()
    private var historyIndexCode: String? = null
    private var historyFetchedAt = 0L
    private var historyBySymbol: Map<String, List<CandleEntry>> = emptyMap()

    suspend operator fun invoke(indexCode: String, timeframe: String): Result<BenchmarkTrend> {
        val history = loadHistory(indexCode)
        val symbols = history.getOrElse { return Result.failure(it) }
        val trend = BenchmarkTrendAggregator.build(indexCode, timeframe, symbols)
            ?: return Result.failure(
                Exception("Not enough constituent history to chart the $timeframe range.")
            )
        return Result.success(trend)
    }

    /** Forces the next call to refetch, used by pull-to-refresh. */
    fun invalidateCache() {
        historyFetchedAt = 0L
    }

    private suspend fun loadHistory(indexCode: String): Result<Map<String, List<CandleEntry>>> =
        historyMutex.withLock {
            val isCached = historyIndexCode == indexCode &&
                historyBySymbol.isNotEmpty() &&
                System.currentTimeMillis() - historyFetchedAt < HISTORY_CACHE_MS
            if (isCached) return@withLock Result.success(historyBySymbol)

            val symbols = constituentsFor(indexCode)
                .getOrNull()
                ?.constituents
                ?.map { it.symbol.trim().uppercase() }
                ?.filter { it.isNotEmpty() }
                ?.distinct()
                .orEmpty()
            if (symbols.isEmpty()) {
                return@withLock Result.failure(Exception("No constituents returned for $indexCode"))
            }

            val fetched = coroutineScope {
                // OkHttp caps this host at 12 concurrent calls and Home's other sections share
                // them, so the fan-out is throttled well below that.
                val permits = Semaphore(MAX_CONCURRENT_HISTORY_CALLS)
                symbols.map { symbol ->
                    async {
                        permits.withPermit {
                            symbol to stockRepository.getPriceHistory(symbol, RAW_HISTORY_RANGE)
                                .getOrNull()
                                .orEmpty()
                        }
                    }
                }.awaitAll()
            }

            val usable: Map<String, List<CandleEntry>> = fetched
                .filter { (_, candles) -> candles.isNotEmpty() }
                .toMap()

            historyIndexCode = indexCode
            historyFetchedAt = System.currentTimeMillis()
            historyBySymbol = usable

            if (usable.isEmpty()) {
                Result.failure(Exception("No price history available for $indexCode constituents"))
            } else {
                Result.success(usable)
            }
        }

    private suspend fun constituentsFor(indexCode: String): Result<IndexConstituents> =
        when (indexCode.replace("-", "").uppercase()) {
            "KSE30" -> marketRepository.getKse30Constituents()
            "KMI30" -> marketRepository.getKmi30Constituents()
            else -> marketRepository.getKse100Constituents()
        }

    private companion object {
        // 1Y is the widest range the backend serves; every narrower window is sliced from it.
        const val RAW_HISTORY_RANGE = "1Y"
        const val MAX_CONCURRENT_HISTORY_CALLS = 6
        const val HISTORY_CACHE_MS = 10 * 60 * 1000L
    }
}
