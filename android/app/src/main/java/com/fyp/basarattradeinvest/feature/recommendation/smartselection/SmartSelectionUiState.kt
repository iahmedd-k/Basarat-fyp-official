package com.fyp.basarattradeinvest.feature.recommendation.smartselection

import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import com.fyp.basarattradeinvest.domain.model.recommendations.TargetStop

data class SmartSelectionUiState(
    val isLoadingCandidates: Boolean = true,
    val candidates: List<StockRecommendation> = emptyList(),
    val candidatesError: String? = null,
    val selectedSymbol: String? = null,
    val isLoadingSetup: Boolean = false,
    val selectedSetup: SmartSelectionSetup? = null,
    val setupMessage: String? = null
)

data class SmartSelectionSetup(
    val recommendation: StockRecommendation,
    val candles: List<CandleEntry>,
    val targetStop: TargetStop?,
    val currentPrice: Double?,
    val targetPrice: Double?,
    val stopLoss: Double?,
    val breakout: BreakoutLevels? = null
)

/**
 * Breakout levels measured from the candles already fetched for this stock: the prior period
 * high/low excluding the newest bar, so the trigger level is never the bar being tested.
 */
data class BreakoutLevels(
    val resistance: Double,
    val support: Double,
    val lastClose: Double,
    val distanceToBreakoutPct: Double,
    val volumeRatio: Double,
    val isConfirmed: Boolean
)
