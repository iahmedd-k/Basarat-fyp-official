package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.data.mapper.StocksDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.StocksApiService
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.FundamentalMetrics
import com.fyp.basarattradeinvest.domain.model.stock.PivotPoints
import com.fyp.basarattradeinvest.domain.model.stock.StockAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.StockDetail
import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult
import com.fyp.basarattradeinvest.domain.model.stock.StockTrade
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalIndicator
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalSignal
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalSummary
import com.fyp.basarattradeinvest.domain.repository.StockRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import java.util.Locale
import kotlin.random.Random

class StockRepositoryImpl(
    private val apiService: StocksApiService = NetworkClient.stocksApiService
) : StockRepository {

    private val stockDatabase = mapOf(
        "SARCO" to StockDetail(
            symbol = "SARCO", code = "2030", companyName = "Saudi Automotive Services Co.",
            sector = "Automobile", price = 58.95, changeAmount = 5.35, changePercent = 9.98,
            marketStatus = "Closed", lastUpdated = "14/09-15:20:00",
            isShariah = true, hasDividend = true, isCompliant = true,
            open = 54.10, high = 59.80, low = 53.60, close = 58.95,
            volume = 867030, avgVolume = 1210000,
            high52Week = 114.50, low52Week = 43.68,
            marketCap = "1.2B", pe = 12.4, eps = 4.75
        ),
        "MEBL" to StockDetail(
            symbol = "MEBL", code = "1001", companyName = "Meezan Bank Limited",
            sector = "Islamic Banking", price = 245.50, changeAmount = 5.20, changePercent = 2.16,
            marketStatus = "Closed", lastUpdated = "14/09-15:30:00",
            isShariah = true, hasDividend = true, isCompliant = true,
            open = 240.00, high = 248.00, low = 239.50, close = 245.50,
            volume = 2400000, avgVolume = 1800000,
            high52Week = 280.00, low52Week = 185.00,
            marketCap = "436.8B", pe = 8.9, eps = 27.58
        ),
        "SYS" to StockDetail(
            symbol = "SYS", code = "1002", companyName = "Systems Limited",
            sector = "Technology", price = 442.80, changeAmount = 24.50, changePercent = 5.86,
            marketStatus = "Closed", lastUpdated = "14/09-15:30:00",
            isShariah = true, hasDividend = true, isCompliant = true,
            open = 420.00, high = 448.00, low = 418.50, close = 442.80,
            volume = 1650000, avgVolume = 1200000,
            high52Week = 520.00, low52Week = 310.00,
            marketCap = "89.5B", pe = 22.1, eps = 20.04
        ),
        "LUCK" to StockDetail(
            symbol = "LUCK", code = "1003", companyName = "Lucky Cement Limited",
            sector = "Cement", price = 912.00, changeAmount = 48.00, changePercent = 5.56,
            marketStatus = "Closed", lastUpdated = "14/09-15:30:00",
            isShariah = true, hasDividend = true, isCompliant = true,
            open = 868.00, high = 918.50, low = 860.00, close = 912.00,
            volume = 980000, avgVolume = 750000,
            high52Week = 950.00, low52Week = 620.00,
            marketCap = "245.8B", pe = 12.4, eps = 73.55
        ),
        "ENGRO" to StockDetail(
            symbol = "ENGRO", code = "1004", companyName = "Engro Corporation",
            sector = "Fertilizer", price = 318.50, changeAmount = 9.80, changePercent = 3.17,
            marketStatus = "Closed", lastUpdated = "14/09-15:30:00",
            isShariah = true, hasDividend = true, isCompliant = true,
            open = 310.00, high = 322.00, low = 308.50, close = 318.50,
            volume = 1100000, avgVolume = 900000,
            high52Week = 380.00, low52Week = 245.00,
            marketCap = "183.6B", pe = 14.2, eps = 22.43
        ),
        "OGDC" to StockDetail(
            symbol = "OGDC", code = "1005", companyName = "Oil & Gas Development Co.",
            sector = "Oil & Gas", price = 154.60, changeAmount = 5.20, changePercent = 3.48,
            marketStatus = "Closed", lastUpdated = "14/09-15:30:00",
            isShariah = true, hasDividend = true, isCompliant = true,
            open = 150.00, high = 156.00, low = 149.00, close = 154.60,
            volume = 3200000, avgVolume = 2800000,
            high52Week = 178.00, low52Week = 112.00,
            marketCap = "664.8B", pe = 6.8, eps = 22.74
        )
    )

    override suspend fun searchStocks(query: String, limit: Int): Result<List<StockSearchResult>> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.searchStocks(query = query, limit = limit)
            if (response.isSuccessful && response.body() != null) {
                val results = response.body()!!.results.orEmpty().map { StocksDtoMapper.mapSearchResult(it) }
                Result.success(results)
            } else {
                fallbackSearch(query)
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            fallbackSearch(query)
        }
    }

    private fun fallbackSearch(query: String): Result<List<StockSearchResult>> {
        val q = query.trim().uppercase()
        val localMatches = stockDatabase.values
            .filter { it.symbol.contains(q, ignoreCase = true) || it.companyName.contains(q, ignoreCase = true) }
            .map { StockSearchResult(symbol = it.symbol, name = it.companyName, sector = it.sector) }
        return Result.success(localMatches)
    }

    override suspend fun getStockOverview(symbol: String): Result<StockDetail> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getStockOverview(symbol)
            if (response.isSuccessful && response.body() != null) {
                Result.success(StocksDtoMapper.mapOverviewToStockDetail(response.body()!!))
            } else {
                fallbackStockDetail(symbol)
            }
        } catch (e: Exception) {
            fallbackStockDetail(symbol)
        }
    }

    override suspend fun getPriceHistory(symbol: String, range: String): Result<List<CandleEntry>> = withContext(Dispatchers.IO) {
        try {
            // Ensure range matches regex ^(1D|1W|1M|1Y)$
            val validRange = when (range.uppercase()) {
                "1D", "DAILY" -> "1D"
                "1W", "WEEKLY" -> "1W"
                "1Y", "YEARLY" -> "1Y"
                else -> "1M"
            }
            val response = apiService.getPriceHistory(symbol = symbol, range = validRange)
            if (response.isSuccessful && response.body() != null) {
                val candles = StocksDtoMapper.mapPriceHistoryToCandles(response.body()!!)
                Result.success(candles)
            } else {
                Result.failure(Exception("Price history not available: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getTechnicalIndicators(symbol: String): Result<TechnicalAnalysis> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getTechnicalIndicators(symbol)
            if (response.isSuccessful && response.body() != null) {
                Result.success(StocksDtoMapper.mapTechnicalIndicators(response.body()!!))
            } else {
                Result.failure(Exception("Technical indicators not available: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getFundamentals(symbol: String): Result<FundamentalMetrics> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getFundamentals(symbol)
            if (response.isSuccessful && response.body() != null) {
                Result.success(StocksDtoMapper.mapFundamentals(response.body()!!))
            } else {
                Result.failure(Exception("Fundamentals not available: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getStockDetail(symbol: String): Result<StockDetail> = getStockOverview(symbol)

    private fun fallbackStockDetail(symbol: String): Result<StockDetail> {
        val stock = stockDatabase[symbol.uppercase()]
        return if (stock != null) {
            Result.success(stock)
        } else {
            Result.success(
                StockDetail(
                    symbol = symbol.uppercase(), code = "0000",
                    companyName = "$symbol Corporation", sector = "General",
                    price = 100.0, changeAmount = 2.50, changePercent = 2.56,
                    marketStatus = "Closed", lastUpdated = "14/09-15:30:00",
                    isShariah = true, hasDividend = true, isCompliant = true,
                    open = 98.00, high = 102.00, low = 97.00, close = 100.00,
                    volume = 500000, avgVolume = 450000,
                    high52Week = 130.00, low52Week = 70.00,
                    marketCap = "10.5B", pe = 10.0, eps = 10.00
                )
            )
        }
    }

    override suspend fun getChartData(symbol: String, timeframe: String): Result<List<CandleEntry>> = withContext(Dispatchers.IO) {
        val stock = stockDatabase[symbol.uppercase()]
        val basePrice = stock?.price?.toFloat() ?: 100f

        val count = when (timeframe) {
            "1D" -> 78
            "Daily" -> 90
            "Weekly", "1W" -> 104
            "1M" -> 60
            "1Y" -> 120
            else -> 90
        }

        val candles = generateMockCandles(basePrice, count, timeframe)
        Result.success(candles)
    }

    override suspend fun getRecentTrades(symbol: String): Result<List<StockTrade>> = withContext(Dispatchers.IO) {
        val stock = stockDatabase[symbol.uppercase()]
        val basePrice = stock?.price ?: 100.0

        val trades = (1..20).map { i ->
            val offset = Random.nextDouble(-2.0, 2.0)
            StockTrade(
                time = "15:${(30 - i).coerceAtLeast(0).toString().padStart(2, '0')}:${Random.nextInt(0, 60).toString().padStart(2, '0')}",
                price = basePrice + offset,
                volume = Random.nextLong(100, 50000),
                type = if (Random.nextBoolean()) "BUY" else "SELL"
            )
        }
        Result.success(trades)
    }

    private fun generateMockCandles(basePrice: Float, count: Int, timeframe: String): List<CandleEntry> {
        val candles = mutableListOf<CandleEntry>()
        var currentPrice = basePrice * 1.4f
        val now = System.currentTimeMillis()

        val intervalMs = when (timeframe) {
            "1D" -> 5 * 60 * 1000L
            "Daily" -> 24 * 60 * 60 * 1000L
            "Weekly", "1W" -> 7 * 24 * 60 * 60 * 1000L
            "1M" -> 30L * 24 * 60 * 60 * 1000L
            "1Y" -> 365L * 24 * 60 * 60 * 1000L
            else -> 24 * 60 * 60 * 1000L
        }

        for (i in count downTo 1) {
            val timestamp = now - (i * intervalMs)
            val volatility = currentPrice * 0.035f
            val change = (Random.nextFloat() - 0.52f) * volatility
            val open = currentPrice
            val close = (currentPrice + change).coerceAtLeast(basePrice * 0.3f)
            val high = maxOf(open, close) + Random.nextFloat() * volatility * 0.5f
            val low = minOf(open, close) - Random.nextFloat() * volatility * 0.5f
            val vol = Random.nextLong(200000, 6000000)

            candles.add(
                CandleEntry(
                    timestamp = timestamp,
                    open = open,
                    high = high,
                    low = low.coerceAtLeast(basePrice * 0.25f),
                    close = close,
                    volume = vol
                )
            )
            currentPrice = close
        }
        return candles
    }

    override suspend fun getStockAnalysis(symbol: String): Result<StockAnalysis> = withContext(Dispatchers.IO) {
        coroutineScope {
            // Fan out the three independent calls concurrently instead of serially.
            val overviewDeferred = async { getStockOverview(symbol) }
            val techDeferred = async { getTechnicalIndicators(symbol) }
            val fundDeferred = async { getFundamentals(symbol) }

            val overviewRes = overviewDeferred.await()
            val techRes = techDeferred.await()
            val fundRes = fundDeferred.await()

            val detail = overviewRes.getOrElse {
                return@coroutineScope Result.failure(it)
            }

            val technical = techRes.getOrElse { emptyTechnicalAnalysis() }
            val fundamentals = fundRes.getOrElse { FundamentalMetrics() }

            Result.success(
                StockAnalysis(
                    symbol = detail.symbol,
                    companyName = detail.companyName,
                    price = detail.price,
                    changeAmount = detail.changeAmount,
                    changePercent = detail.changePercent,
                    technical = technical,
                    fundamentals = fundamentals
                )
            )
        }
    }

    private fun emptyTechnicalAnalysis(): TechnicalAnalysis {
        return TechnicalAnalysis(
            summary = TechnicalSummary(
                overallSignal = TechnicalSignal.NEUTRAL,
                buyCount = 0,
                neutralCount = 0,
                sellCount = 0
            ),
            oscillators = emptyList(),
            movingAverages = emptyList(),
            pivotPoints = PivotPoints(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        )
    }
}
