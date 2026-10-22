package com.fyp.basarattradeinvest.feature.sentiment

import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentimentOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistory
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsItem
import com.fyp.basarattradeinvest.domain.model.sentiment.StockSentiment

// ─────────────────────────────────────────────────────────────────────────────
// SentimentUiState
//
// Independent state for each of the 4 sentiment sections.
// One section failing does NOT block others from showing data.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Root screen state. Holds per-section states so each loads independently.
 */
data class SentimentScreenState(
    val symbol: String = "",
    val marketSentiment: MarketSentimentSectionState = MarketSentimentSectionState.Loading,
    val stockSentiment: StockSentimentSectionState = StockSentimentSectionState.Loading,
    val history: SentimentHistorySectionState = SentimentHistorySectionState.Loading,
    val news: SentimentNewsSectionState = SentimentNewsSectionState.Loading,
    val selectedPeriod: String = "1M"
)

// ─── Market Sentiment Section ──────────────────────────────────────────────

sealed interface MarketSentimentSectionState {
    data object Loading : MarketSentimentSectionState
    data class Success(val data: MarketSentimentOverview) : MarketSentimentSectionState
    data object Empty : MarketSentimentSectionState
    data class Error(val message: String) : MarketSentimentSectionState
}

// ─── Stock Sentiment Section ───────────────────────────────────────────────

sealed interface StockSentimentSectionState {
    data object Loading : StockSentimentSectionState
    data class Success(val data: StockSentiment) : StockSentimentSectionState
    data object Empty : StockSentimentSectionState
    data class Error(val message: String) : StockSentimentSectionState
}

// ─── Sentiment History Section ─────────────────────────────────────────────

sealed interface SentimentHistorySectionState {
    data object Loading : SentimentHistorySectionState
    data class Success(val data: SentimentHistory) : SentimentHistorySectionState
    data object Empty : SentimentHistorySectionState
    data class Error(val message: String) : SentimentHistorySectionState
}

// ─── Sentiment News Section ────────────────────────────────────────────────

/**
 * News state includes pagination cursor.
 * items accumulates across pages (no duplicates by id).
 * isLoadingMore is separate from the initial Loading state.
 */
sealed interface SentimentNewsSectionState {
    data object Loading : SentimentNewsSectionState

    data class Success(
        val items: List<SentimentNewsItem>,
        val currentPage: Int,
        val hasMore: Boolean,
        val isLoadingMore: Boolean = false
    ) : SentimentNewsSectionState

    data object Empty : SentimentNewsSectionState
    data class Error(val message: String) : SentimentNewsSectionState
}
