package com.fyp.basarattradeinvest.feature.stock.detail

import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights
import com.fyp.basarattradeinvest.domain.model.recommendations.ExpectedPriceRange
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationDetail
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationSignal
import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import com.fyp.basarattradeinvest.domain.model.recommendations.TargetStop
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class StockDetailViewModelTest {

    @Before
    fun setUp() {
        // viewModelScope launches on Dispatchers.Main, which has no looper in JVM tests.
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private class FakeRecommendationsRepository : RecommendationsRepository {
        override suspend fun getRecommendations(
            riskProfile: String?,
            sector: String?,
            limit: Int
        ): Result<List<StockRecommendation>> = Result.success(emptyList())

        override suspend fun getRecommendationDetail(symbol: String, knownPrice: Double?): Result<RecommendationDetail> =
            Result.success(
                RecommendationDetail(
                    symbol = symbol,
                    signal = RecommendationSignal.BUY,
                    confidence = 0.82,
                    compositeScore = 0.72,
                    individualSignals = mapOf("ml" to 0.8, "technical" to 0.7, "fundamental" to 0.75),
                    targetPrice = 120.0,
                    stopLoss = 95.0,
                    expectedRange = ExpectedPriceRange(90.0, 130.0, "atr_range"),
                    currentPrice = 100.0,
                    atr14 = 8.0,
                    reasoning = mapOf("ml" to mapOf("direction" to "Bullish")),
                    weights = mapOf("ml" to 0.5, "technical" to 0.3, "fundamental" to 0.2)
                )
            )

        override suspend fun getTargetStop(symbol: String, knownPrice: Double?): Result<TargetStop> =
            Result.success(
                TargetStop(
                    symbol = symbol,
                    currentPrice = 100.0,
                    targetPrice = 120.0,
                    stopLoss = 95.0,
                    expectedRange = ExpectedPriceRange(90.0, 130.0, "atr_range"),
                    method = "atr_range",
                    atr14 = 8.0,
                    riskTolerance = "moderate",
                    upsidePct = 20.0,
                    downsidePct = -5.0
                )
            )

        override suspend fun getEngineWeights(): Result<EngineWeights> =
            Result.success(EngineWeights(0.33, 0.33, 0.34))

        override suspend fun setEngineWeights(
            gruWeight: Double,
            technicalWeight: Double,
            fundamentalWeight: Double
        ): Result<EngineWeights> = Result.success(EngineWeights(gruWeight, technicalWeight, fundamentalWeight))
    }

    @Test
    fun `recommendation card keeps the same symbol state across price updates`() = runBlocking {
        val viewModel = StockDetailViewModel(
            recommendationsRepository = FakeRecommendationsRepository()
        )

        viewModel.loadRecommendationCard("TEST")
        delay(50)

        val firstState = viewModel.recommendationCardState.value
        assertTrue(firstState is RecommendationCardUiState.Success)
        assertEquals("TEST", (firstState as RecommendationCardUiState.Success).symbol)

        viewModel.loadRecommendationCard("TEST", 101.5)
        delay(50)

        val nextState = viewModel.recommendationCardState.value
        assertTrue(nextState is RecommendationCardUiState.Success)
        assertEquals("TEST", (nextState as RecommendationCardUiState.Success).symbol)
    }
}
