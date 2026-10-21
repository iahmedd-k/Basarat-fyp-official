package com.fyp.basarattradeinvest.feature.etf

import com.fyp.basarattradeinvest.domain.model.etf.EtfHistoryEntry
import com.fyp.basarattradeinvest.domain.model.etf.EtfItem
import com.fyp.basarattradeinvest.domain.model.etf.EtfPerformance

enum class EtfDetailTab { OVERVIEW, HISTORY, PERFORMANCE }

sealed interface EtfHistoryUiState {
    data object Loading : EtfHistoryUiState
    data class Success(val entries: List<EtfHistoryEntry>) : EtfHistoryUiState
    data object Empty : EtfHistoryUiState
    data class Error(val message: String) : EtfHistoryUiState
}

sealed interface EtfPerformanceUiState {
    data object Loading : EtfPerformanceUiState
    data class Success(val performance: EtfPerformance) : EtfPerformanceUiState
    data class Error(val message: String) : EtfPerformanceUiState
}

sealed interface EtfDetailUiState {
    data object Loading : EtfDetailUiState
    data class Success(
        val etf: EtfItem,
        val selectedTab: EtfDetailTab = EtfDetailTab.OVERVIEW,
        val historyState: EtfHistoryUiState = EtfHistoryUiState.Loading,
        val performanceState: EtfPerformanceUiState = EtfPerformanceUiState.Loading,
        val selectedTimeframe: String = "1M"
    ) : EtfDetailUiState
    data class Error(val message: String) : EtfDetailUiState
}
