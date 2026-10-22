package com.fyp.basarattradeinvest.forecast

import com.fyp.basarattradeinvest.data.mapper.ForecastDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.ForecastApiService
import com.fyp.basarattradeinvest.data.remote.dto.forecast.*
import com.fyp.basarattradeinvest.data.repository.ForecastRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.stock.ForecastDirection
import com.fyp.basarattradeinvest.domain.usecase.forecast.GetForecastHistoryUseCase
import com.fyp.basarattradeinvest.domain.usecase.forecast.GetStockForecastUseCase
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Response

class ForecastModuleUnitTest {

    private val gson = Gson()

    // 1. JSON Parsing Tests against Swagger definitions
    @Test
    fun testForecastResponseDtoParsing() {
        val json = """
        {
          "symbol": "LUCK",
          "horizon": "1D",
          "direction": "bullish",
          "confidence": 0.842,
          "current_price": 412.80,
          "target_price": 435.50,
          "target_date": "2026-03-24",
          "as_of_date": "2026-03-23",
          "stop_loss": 398.00,
          "upside_pct": 5.5,
          "downside_pct": -3.6,
          "risk_reward_ratio": 1.53,
          "signal_rating": "Strong Buy",
          "model_version": "ensemble",
          "gate_reason": "agree(bullish)",
          "probabilities": {
            "bullish": 55.4,
            "bearish": 19.8,
            "sideways": 24.8
          },
          "models": {
            "gru": {
              "direction": "bullish",
              "bullish_pct": 52.0,
              "bearish_pct": 20.0,
              "sideways_pct": 28.0,
              "gap_pp": 24.0
            },
            "xgb": {
              "direction": "bullish",
              "bullish_pct": 58.8,
              "bearish_pct": 19.6,
              "sideways_pct": 21.6,
              "gap_pp": 37.2
            }
          },
          "market_context": {
            "market_return_5d": 0.012,
            "market_return_20d": 0.034,
            "stock_return_20d": -0.058,
            "stock_relative_return_20d": -0.092
          }
        }
        """.trimIndent()

        val dto = gson.fromJson(json, ForecastResponseDto::class.java)
        assertNotNull(dto)
        assertEquals("LUCK", dto.symbol)
        assertEquals("1D", dto.horizon)
        assertEquals("bullish", dto.direction)
        assertEquals(0.842, dto.confidence, 0.001)
        assertEquals(412.80, dto.currentPrice ?: 0.0, 0.01)
        assertEquals(435.50, dto.targetPrice ?: 0.0, 0.01)
        assertEquals("Strong Buy", dto.signalRating)
        assertEquals("ensemble", dto.modelVersion)
        assertEquals("agree(bullish)", dto.gateReason)
        assertEquals(55.4, dto.probabilities?.bullish ?: 0.0, 0.01)
        assertEquals("bullish", dto.models?.get("gru")?.direction)
        assertEquals(0.012, dto.marketContext?.marketReturn5d ?: 0.0, 0.001)
    }

    @Test
    fun testForecastHistoryResponseDtoParsing() {
        val json = """
        {
          "symbol": "LUCK",
          "horizon": "1D",
          "count": 2,
          "accuracy": 0.75,
          "history": [
            {
              "predicted_at": "2026-03-22T09:30:00Z",
              "predicted_direction": "bullish",
              "probabilities": { "bullish": 60.0, "bearish": 20.0, "sideways": 20.0 },
              "confidence": 0.85,
              "target_date": "2026-03-23",
              "actual": {
                "direction": "bullish",
                "was_correct": true
              }
            },
            {
              "predicted_at": "2026-03-21T09:30:00Z",
              "predicted_direction": "bearish",
              "probabilities": { "bullish": 25.0, "bearish": 55.0, "sideways": 20.0 },
              "confidence": 0.70,
              "target_date": "2026-03-22",
              "actual": {
                "direction": "bullish",
                "was_correct": false
              }
            }
          ]
        }
        """.trimIndent()

        val dto = gson.fromJson(json, ForecastHistoryResponseDto::class.java)
        assertNotNull(dto)
        assertEquals("LUCK", dto.symbol)
        assertEquals(2, dto.count)
        assertEquals(0.75, dto.accuracy ?: 0.0, 0.01)
        assertEquals(2, dto.history!!.size)
        assertEquals("bullish", dto.history!![0].predictedDirection)
        assertTrue(dto.history!![0].actual?.wasCorrect == true)
        assertFalse(dto.history!![1].actual?.wasCorrect == true)
    }

    // 2. Mapper Tests
    @Test
    fun testForecastDtoMapper() {
        val dto = ForecastResponseDto(
            symbol = "OGDC",
            horizon = "1W",
            direction = "bullish",
            confidence = 0.79,
            currentPrice = 145.20,
            targetPrice = 152.00,
            targetDate = "2026-03-30",
            asOfDate = "2026-03-23",
            stopLoss = 140.00,
            upsidePct = 4.68,
            downsidePct = -3.58,
            riskRewardRatio = 1.31,
            signalRating = "Buy",
            modelVersion = "gru_v1",
            gateReason = "single_model",
            probabilities = ForecastProbabilitiesDto(bullish = 65.0, bearish = 15.0, sideways = 20.0),
            models = mapOf(
                "gru" to ForecastModelDetailDto(
                    direction = "bullish",
                    bullishPct = 65.0,
                    bearishPct = 15.0,
                    sidewaysPct = 20.0,
                    gapPp = 45.0
                )
            ),
            marketContext = ForecastMarketContextDto(
                marketReturn5d = 0.02,
                marketReturn20d = 0.05,
                stockReturn20d = 0.03,
                stockRelativeReturn20d = -0.02
            )
        )

        val domain = ForecastDtoMapper.mapToDomain(dto)
        assertEquals("OGDC", domain.symbol)
        assertEquals(ForecastDirection.BULLISH, domain.direction)
        assertEquals(0.79, domain.confidence, 0.01)
        assertEquals(152.00, domain.targetPrice ?: 0.0, 0.01)
        assertEquals("Buy", domain.signalRating)
        assertEquals(65.0, domain.probabilities?.bullish ?: 0.0, 0.01)
        assertEquals(1, domain.models.size)
        assertEquals("bullish", domain.models["gru"]?.direction)
        assertEquals(0.02, domain.marketContext?.marketReturn5d ?: 0.0, 0.001)
    }

    @Test
    fun testForecastDtoMapper_leavesLevelsNullWhenBackendWithholdsThem() {
        // Reproduces the exact backend scenario from user screenshot:
        // direction is "sideways", gateReason is "near_tie", confidence 61%, target_price/stop_loss are null
        val dto = ForecastResponseDto(
            symbol = "OGDC",
            horizon = "1D",
            direction = "sideways",
            confidence = 0.61,
            targetDate = "2026-09-18",
            asOfDate = "2026-09-17",
            currentPrice = 106.99,
            targetPrice = null,
            stopLoss = null,
            upsidePct = null,
            downsidePct = null,
            riskRewardRatio = null,
            probabilities = ForecastProbabilitiesDto(bullish = 61.0, bearish = 39.0, sideways = 0.0)
        )

        val domain = ForecastDtoMapper.mapToDomain(dto)

        // The mapper used to synthesise a target/stop from direction, horizon and confidence.
        // Those were invented figures, so they are gone: absent levels stay absent.
        assertNull(domain.targetPrice)
        assertNull(domain.stopLoss)
        assertNull(domain.upsidePct)
        assertNull(domain.downsidePct)
        assertNull(domain.riskRewardRatio)
        assertEquals(106.99, domain.currentPrice!!, 0.001)
    }

    @Test
    fun testForecastRecalculateTargetsWithFallbackPrice() {
        // When backend currentPrice is null, recalculateTargets uses live quote price
        val dto = ForecastResponseDto(
            symbol = "LUCK",
            horizon = "1W",
            direction = "bullish",
            confidence = 0.75,
            targetDate = "2026-09-25",
            asOfDate = "2026-09-18",
            currentPrice = null,
            targetPrice = null,
            stopLoss = null
        )

        val initialDomain = ForecastDtoMapper.mapToDomain(dto)
        assertNull(initialDomain.currentPrice)

        val recalculated = ForecastDtoMapper.recalculateTargets(initialDomain, livePrice = 420.00)
        assertEquals(420.00, recalculated.currentPrice ?: 0.0, 0.01)
        // Only the quote is filled in from the live price; the levels come from the API or not at all.
        assertNull(recalculated.targetPrice)
        assertNull(recalculated.stopLoss)
    }

    // 3. Repository Tests
    @Test
    fun testForecastRepositorySuccess() = runBlocking {
        val fakeApi = object : ForecastApiService {
            override suspend fun getStockForecast(symbol: String, horizon: String?): Response<ForecastResponseDto> {
                return Response.success(
                    ForecastResponseDto(
                        symbol = symbol,
                        horizon = horizon ?: "1D",
                        direction = "bullish",
                        confidence = 0.88,
                        targetDate = "2026-03-24",
                        asOfDate = "2026-03-23"
                    )
                )
            }

            override suspend fun getForecastHistory(symbol: String, horizon: String?, limit: Int?): Response<ForecastHistoryResponseDto> {
                return Response.success(
                    ForecastHistoryResponseDto(
                        symbol = symbol,
                        count = 1,
                        accuracy = 0.85,
                        history = listOf(
                            ForecastHistoryItemDto(
                                predictedAt = "2026-03-22T00:00:00Z",
                                predictedDirection = "bullish",
                                confidence = 0.85,
                                targetDate = "2026-03-23",
                                actual = ForecastActualOutcomeDto(direction = "bullish", wasCorrect = true)
                            )
                        )
                    )
                )
            }
        }

        val repo = ForecastRepositoryImpl(fakeApi)

        val forecastResult = repo.getStockForecast("LUCK", "1D")
        assertTrue(forecastResult.isSuccess)
        val forecast = forecastResult.getOrThrow()
        assertEquals("LUCK", forecast.symbol)
        assertEquals(ForecastDirection.BULLISH, forecast.direction)

        val historyResult = repo.getForecastHistory("LUCK", horizon = "1W", limit = 30)
        assertTrue(historyResult.isSuccess)
        val history = historyResult.getOrThrow()
        assertEquals(1, history.count)
        assertEquals(0.85, history.accuracy ?: 0.0, 0.01)
    }

    @Test
    fun testForecastRepositoryErrorHandling() = runBlocking {
        val fakeApi = object : ForecastApiService {
            override suspend fun getStockForecast(symbol: String, horizon: String?): Response<ForecastResponseDto> {
                val errorBody = "{\"message\":\"Unauthorized\"}".toResponseBody("application/json".toMediaType())
                return Response.error(401, errorBody)
            }

            override suspend fun getForecastHistory(symbol: String, horizon: String?, limit: Int?): Response<ForecastHistoryResponseDto> {
                val errorBody = "{\"message\":\"Not found\"}".toResponseBody("application/json".toMediaType())
                return Response.error(404, errorBody)
            }
        }

        val repo = ForecastRepositoryImpl(fakeApi)

        val forecastResult = repo.getStockForecast("UNKNOWN", "1D")
        assertTrue(forecastResult.isFailure)
        assertTrue(forecastResult.exceptionOrNull()?.message?.contains("Session expired") == true)

        val historyResult = repo.getForecastHistory("UNKNOWN", horizon = "1W", limit = 30)
        assertTrue(historyResult.isFailure)
        assertTrue(historyResult.exceptionOrNull()?.message?.contains("not found") == true)
    }

    // 4. UseCase Validation Tests
    @Test
    fun testUseCasesValidation() = runBlocking {
        val fakeApi = object : ForecastApiService {
            override suspend fun getStockForecast(symbol: String, horizon: String?): Response<ForecastResponseDto> {
                return Response.success(
                    ForecastResponseDto(
                        symbol = symbol,
                        horizon = horizon ?: "1D",
                        direction = "bullish",
                        confidence = 0.8,
                        targetDate = "2026-03-24",
                        asOfDate = "2026-03-23"
                    )
                )
            }

            override suspend fun getForecastHistory(symbol: String, horizon: String?, limit: Int?): Response<ForecastHistoryResponseDto> {
                return Response.success(
                    ForecastHistoryResponseDto(
                        symbol = symbol,
                        count = 0,
                        history = emptyList()
                    )
                )
            }
        }

        val repo = ForecastRepositoryImpl(fakeApi)
        val getForecastUseCase = GetStockForecastUseCase(repo)
        val getHistoryUseCase = GetForecastHistoryUseCase(repo)

        // Blank symbol handling
        val blankForecastResult = getForecastUseCase("   ")
        assertTrue(blankForecastResult.isFailure)
        assertEquals("Stock symbol cannot be blank", blankForecastResult.exceptionOrNull()?.message)

        val blankHistoryResult = getHistoryUseCase("")
        assertTrue(blankHistoryResult.isFailure)
        assertEquals("Stock symbol cannot be blank", blankHistoryResult.exceptionOrNull()?.message)

        // Valid execution with whitespace trimming and uppercase
        val validForecastResult = getForecastUseCase(" luck ")
        assertTrue(validForecastResult.isSuccess)
        assertEquals("LUCK", validForecastResult.getOrThrow().symbol)
    }
}
