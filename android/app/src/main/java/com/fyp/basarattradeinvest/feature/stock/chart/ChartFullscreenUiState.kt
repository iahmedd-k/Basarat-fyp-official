package com.fyp.basarattradeinvest.feature.stock.chart

import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.StockDetail

sealed interface ChartFullscreenUiState {
    data object Loading : ChartFullscreenUiState

    data class Success(
        val stockDetail: StockDetail,
        val candles: List<CandleEntry>,
        val selectedTimeframe: String,
        val activeIndicators: Set<String>,
        val selectedTool: DrawingTool = DrawingTool.CROSSHAIR
    ) : ChartFullscreenUiState

    data object Empty : ChartFullscreenUiState

    data class Error(val message: String) : ChartFullscreenUiState
}

enum class DrawingTool {
    CROSSHAIR,
    TRENDLINE,
    HORIZONTAL_RAY,
    NONE
}
