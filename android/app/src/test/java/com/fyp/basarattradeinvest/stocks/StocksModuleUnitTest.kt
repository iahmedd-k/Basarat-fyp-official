package com.fyp.basarattradeinvest.stocks

import com.fyp.basarattradeinvest.data.mapper.StocksDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.StocksApiService
import com.fyp.basarattradeinvest.data.remote.dto.stocks.*
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalSignal
import com.fyp.basarattradeinvest.domain.usecase.stocks.SearchStocksUseCase
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Response

class StocksModuleUnitTest {

    private val gson = Gson()

    @Test
    fun testStockSearchDto_deserializationAndMapping() {
        val json = """
            {
                "results": [
                    { "symbol": "LUCK", "name": "Lucky Cement Limited", "sector": "Cement" },
                    { "symbol": "OGDC", "name": "Oil & Gas Development", "sector": "Oil & Gas" }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, StockSearchResponseDto::class.java)
        assertEquals(2, dto.results!!.size)
        assertEquals("LUCK", dto.results!![0].symbol)

        val domain = StocksDtoMapper.mapSearchResult(dto.results!![0])
        assertEquals("LUCK", domain.symbol)
        assertEquals("Lucky Cement Limited", domain.name)
        assertEquals("Cement", domain.sector)
    }

    @Test
    fun testStockOverviewDto_deserializationAndMapping() {
        val json = """
            {
                "symbol": "OGDC",
                "name": "Oil & Gas Development Company Limited",
                "sector": "Oil & Gas Exploration Companies",
                "ltp": 154.6,
                "ldcp": 149.4,
                "change": 5.2,
                "change_pct": 3.48,
                "day_range": { "low": 149.0, "high": 156.0 },
                "volume": 3200000,
                "market_cap_m": 664800.0,
                "pe_ratio": 6.8,
                "year_change_pct": 25.4,
                "ytd_change_pct": 18.2
            }
        """.trimIndent()

        val dto = gson.fromJson(json, StockOverviewDto::class.java)
        assertEquals("OGDC", dto.symbol)
        assertEquals(154.6, dto.ltp!!, 0.001)

        val detail = StocksDtoMapper.mapOverviewToStockDetail(dto)
        assertEquals("OGDC", detail.symbol)
        assertEquals(154.6, detail.price, 0.001)
        assertEquals(5.2, detail.changeAmount, 0.001)
        assertEquals(3.48, detail.changePercent, 0.001)
        assertEquals(149.0, detail.low, 0.001)
        assertEquals(156.0, detail.high, 0.001)
        assertEquals(3200000L, detail.volume)
        assertEquals(6.8, detail.pe, 0.001)
    }

    @Test
    fun testPriceHistoryDto_deserializationAndMapping() {
        val json = """
            {
                "symbol": "LUCK",
                "range": "1M",
                "bars": [
                    { "date": "2026-09-01", "open": 900.0, "high": 920.0, "low": 895.0, "close": 915.0, "volume": 1200000 },
                    { "date": "2026-09-02", "open": 915.0, "high": 925.0, "low": 910.0, "close": 918.0, "volume": 980000 }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, PriceHistoryResponseDto::class.java)
        assertEquals("LUCK", dto.symbol)
        assertEquals(2, dto.bars!!.size)

        val candles = StocksDtoMapper.mapPriceHistoryToCandles(dto)
        assertEquals(2, candles.size)
        assertEquals(900.0f, candles[0].open, 0.001f)
        assertEquals(920.0f, candles[0].high, 0.001f)
        assertEquals(895.0f, candles[0].low, 0.001f)
        assertEquals(915.0f, candles[0].close, 0.001f)
        assertEquals(1200000L, candles[0].volume)
    }

    @Test
    fun testTechnicalIndicatorsDto_deserializationAndMapping() {
        val json = """
            {
                "symbol": "SYS",
                "period": 14,
                "overall_signal": "BUY",
                "summary_message": "Technical indicators suggest an upward momentum.",
                "signals_breakdown": {
                    "buy": 12,
                    "neutral": 3,
                    "sell": 1
                },
                "summary": {
                    "rsi": { "value": 64.5, "signal": "BUY", "description": "RSI shows bullish momentum" },
                    "macd": { "value": 3.8, "signal": "BUY", "description": "Bullish crossover" },
                    "sma": { "sma_20": 435.0, "signal": "BUY", "description": "Price above 20 SMA" },
                    "bollinger": { "middle_band": 430.0, "signal": "NEUTRAL", "description": "Normal volatility" },
                    "adx": { "value": 31.2, "signal": "BUY", "description": "Strong trend" }
                }
            }
        """.trimIndent()

        val dto = gson.fromJson(json, TechnicalIndicatorsResponseDto::class.java)
        assertEquals("SYS", dto.symbol)
        assertEquals("BUY", dto.overallSignal)

        val tech = StocksDtoMapper.mapTechnicalIndicators(dto)
        assertEquals(TechnicalSignal.BUY, tech.summary.overallSignal)
        assertEquals(12, tech.summary.buyCount)
        assertEquals(3, tech.summary.neutralCount)
        assertEquals(1, tech.summary.sellCount)
        assertTrue(tech.oscillators.any { it.name.startsWith("RSI") && it.signal == TechnicalSignal.BUY })
        assertTrue(tech.oscillators.any { it.name.startsWith("MACD") && it.signal == TechnicalSignal.BUY })
    }

    @Test
    fun testFundamentalsDto_deserializationAndMapping() {
        val json = """
            {
                "symbol": "MEBL",
                "company_profile": {
                    "name": "Meezan Bank Limited",
                    "sector": "Islamic Banking",
                    "business_description": "Premier Islamic Bank in Pakistan"
                },
                "equity_profile": {
                    "market_cap_pkr_m": 436800.0,
                    "total_shares": 1780000000,
                    "free_float_pct": 45.5
                },
                "financial_ratios": {
                    "pe_ratio": 8.9,
                    "peg_ratio": 0.65,
                    "eps": 27.58,
                    "eps_growth_pct": 22.4,
                    "net_profit_margin_pct": 32.1,
                    "dividend_yield_pct": 7.5
                },
                "extras": {
                    "debt_to_equity": 0.12,
                    "current_ratio": 1.45,
                    "quick_ratio": 1.2,
                    "roe_pct": 35.4,
                    "roa_pct": 2.8,
                    "interest_coverage": 14.2
                }
            }
        """.trimIndent()

        val dto = gson.fromJson(json, FundamentalsResponseDto::class.java)
        assertEquals("MEBL", dto.symbol)

        val fundamentals = StocksDtoMapper.mapFundamentals(dto)
        assertEquals(8.9, fundamentals.peRatio!!, 0.001)
        assertEquals(0.65, fundamentals.pegRatio!!, 0.001)
        assertEquals(27.58, fundamentals.eps!!, 0.001)
        assertEquals(7.5, fundamentals.dividendYield!!, 0.001)
        assertEquals(35.4, fundamentals.roe!!, 0.001)
        assertEquals(0.12, fundamentals.debtToEquity!!, 0.001)
    }

    @Test
    fun testHBLFundamentalsMapping_partialData() {
        val json = """
            {
              "symbol": "HBL",
              "data_status": "partial",
              "data_message": "Some company fundamentals are missing from the upstream PSX feed; blank fields are not estimated.",
              "company_profile": {
                "name": "Habib Bank",
                "sector": "COMMERCIAL BANKS"
              },
              "ratios": {
                "pe_ratio": null,
                "peg_ratio": null,
                "eps": null,
                "dividend_yield_pct": 7.8
              },
              "metrics": [
                { "key": "EPS", "value": null },
                { "key": "P/E Ratio", "value": null },
                { "key": "Dividend Yield", "value": 7.8 }
              ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, FundamentalsResponseDto::class.java)
        assertEquals("HBL", dto.symbol)
        assertEquals("partial", dto.dataStatus)

        val fundamentals = StocksDtoMapper.mapFundamentals(dto)
        assertNull(fundamentals.peRatio)
        assertNull(fundamentals.eps)
        assertEquals(7.8, fundamentals.dividendYield!!, 0.001)
    }

    @Test
    fun testSearchStocksUseCase_emptyQueryReturnsEmptyList() = runBlocking {
        val mockRepo = StockRepositoryImpl()
        val useCase = SearchStocksUseCase(mockRepo)

        val result = useCase("")
        assertTrue(result.isSuccess)
        assertTrue(result.getOrThrow().isEmpty())

        val whitespaceResult = useCase("   ")
        assertTrue(whitespaceResult.isSuccess)
        assertTrue(whitespaceResult.getOrThrow().isEmpty())
    }

    @Test
    fun testStockRepositoryImpl_offlineFallback() = runBlocking {
        val mockApi = object : StocksApiService {
            override suspend fun searchStocks(query: String, limit: Int): Response<StockSearchResponseDto> {
                return Response.error(500, "Server Error".toResponseBody())
            }
            override suspend fun getStockOverview(symbol: String): Response<StockOverviewDto> {
                return Response.error(500, "Server Error".toResponseBody())
            }
            override suspend fun getPriceHistory(symbol: String, range: String): Response<PriceHistoryResponseDto> {
                return Response.error(500, "Server Error".toResponseBody())
            }
            override suspend fun getTechnicalIndicators(symbol: String, indicators: String, period: Int, limit: Int): Response<TechnicalIndicatorsResponseDto> {
                return Response.error(500, "Server Error".toResponseBody())
            }
            override suspend fun getFundamentals(symbol: String): Response<FundamentalsResponseDto> {
                return Response.error(500, "Server Error".toResponseBody())
            }
        }

        val repository = StockRepositoryImpl(mockApi)

        // Test fallback search
        val searchRes = repository.searchStocks("LUCK")
        assertTrue(searchRes.isSuccess)
        assertTrue(searchRes.getOrThrow().any { it.symbol == "LUCK" })

        // Test fallback stock overview
        val overviewRes = repository.getStockOverview("OGDC")
        assertTrue(overviewRes.isSuccess)
        assertEquals("OGDC", overviewRes.getOrThrow().symbol)

        // Test price history on API error (strict no-mock rule: fails rather than inventing fake candles)
        val historyRes = repository.getPriceHistory("OGDC", "1M")
        assertTrue(historyRes.isFailure)

        // Test technical indicators on API error (strict no-mock rule: fails rather than inventing fake RSI/MACD)
        val techRes = repository.getTechnicalIndicators("OGDC")
        assertTrue(techRes.isFailure)

        // Test fundamentals on API error (strict no-mock rule: fails rather than inventing fake multiples)
        val fundRes = repository.getFundamentals("OGDC")
        assertTrue(fundRes.isFailure)
    }
}
