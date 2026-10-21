package com.fyp.basarattradeinvest.feature.stock.analysis

import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.ForecastHistory
import com.fyp.basarattradeinvest.domain.model.stock.StockAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.StockForecast
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistory
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsItem
import com.fyp.basarattradeinvest.domain.model.sentiment.StockSentiment

sealed interface StockAnalysisUiState {
    data object Loading : StockAnalysisUiState

    data class Success(
        val analysis: StockAnalysis,
        val selectedTab: AnalysisTab = AnalysisTab.TECHNICAL,
        val selectedPriceRange: String = "1M",
        val priceHistoryState: PriceHistorySectionState = PriceHistorySectionState.Loading,
        val selectedHorizon: String = "1D",
        val forecastState: ForecastSectionState = ForecastSectionState.Loading,
        val historyState: ForecastHistorySectionState = ForecastHistorySectionState.Loading,
        val sentimentState: StockSentimentSectionState = StockSentimentSectionState.Loading,
        val sentimentHistoryState: SentimentHistorySectionState = SentimentHistorySectionState.Loading,
        val sentimentNewsState: SentimentNewsSectionState = SentimentNewsSectionState.Loading
    ) : StockAnalysisUiState

    data object Empty : StockAnalysisUiState

    data class Error(
        val message: String
    ) : StockAnalysisUiState
}

enum class AnalysisTab {
    TECHNICAL,
    FUNDAMENTALS,
    FORECAST,
    SENTIMENT
}

sealed interface PriceHistorySectionState {
    data object Loading : PriceHistorySectionState
    data class Success(val candles: List<CandleEntry>) : PriceHistorySectionState
    data object Empty : PriceHistorySectionState
    data class Error(val message: String) : PriceHistorySectionState
}

sealed interface ForecastSectionState {
    data object Loading : ForecastSectionState
    data class Success(val forecast: StockForecast) : ForecastSectionState
    data object Empty : ForecastSectionState
    data class Error(val message: String) : ForecastSectionState
}

sealed interface ForecastHistorySectionState {
    data object Loading : ForecastHistorySectionState
    data class Success(val history: ForecastHistory) : ForecastHistorySectionState
    data object Empty : ForecastHistorySectionState
    data class Error(val message: String) : ForecastHistorySectionState
}

sealed interface StockSentimentSectionState {
    data object Loading : StockSentimentSectionState
    data class Success(val sentiment: StockSentiment) : StockSentimentSectionState
    data object Empty : StockSentimentSectionState
    data class Error(val message: String) : StockSentimentSectionState
}

sealed interface SentimentHistorySectionState {
    data object Loading : SentimentHistorySectionState
    data class Success(val history: SentimentHistory) : SentimentHistorySectionState
    data object Empty : SentimentHistorySectionState
    data class Error(val message: String) : SentimentHistorySectionState
}

sealed interface SentimentNewsSectionState {
    data object Loading : SentimentNewsSectionState
    data class Success(val news: List<SentimentNewsItem>) : SentimentNewsSectionState
    data object Empty : SentimentNewsSectionState
    data class Error(val message: String) : SentimentNewsSectionState
}
