package com.fyp.basarattradeinvest.feature.stock.detail

import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.StockAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.StockDetail
import com.fyp.basarattradeinvest.domain.model.stock.StockForecast
import com.fyp.basarattradeinvest.domain.model.stock.StockTrade
import com.fyp.basarattradeinvest.domain.model.live.WsConnectionState

sealed interface StockDetailUiState {
    data object Loading : StockDetailUiState

    data class Success(
        val detail: StockDetail,
        val candles: List<CandleEntry>,
        val trades: List<StockTrade>,
        val selectedTimeframe: String,
        val selectedSection: String,   // "Quotes", "Analysis", "News", "Profile"
        val selectedSubPill: String,   // Quotes: "By Price", "Trades", "Detailed Quote", "Liquidity" | Analysis: "Technicals", "AI Forecast", "Fundamentals", "Shariah"
        val analysis: StockAnalysis? = null,
        val forecast: StockForecast? = null,
        val isAnalysisLoading: Boolean = false,
        val livePrice: Double? = null,
        val liveChangePct: Double? = null,
        val liveChange: Double? = null,
        val liveVolume: Long? = null,
        val isLivePriceStreaming: Boolean = false,
        val liveIsStale: Boolean = false,
        val wsConnectionState: WsConnectionState = WsConnectionState.Idle
    ) : StockDetailUiState

    data object Empty : StockDetailUiState

    data class Error(val message: String) : StockDetailUiState
}

