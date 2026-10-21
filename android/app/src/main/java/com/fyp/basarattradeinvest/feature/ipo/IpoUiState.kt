package com.fyp.basarattradeinvest.feature.ipo

import com.fyp.basarattradeinvest.domain.model.ipo.IpoCalendarEvent
import com.fyp.basarattradeinvest.domain.model.ipo.IpoItem
import com.fyp.basarattradeinvest.domain.model.ipo.IpoPerformanceSummary

sealed interface IpoDirectoryUiState {
    data object Loading : IpoDirectoryUiState
    data class Success(val items: List<IpoItem>) : IpoDirectoryUiState
    data object Empty : IpoDirectoryUiState
    data class Error(val message: String) : IpoDirectoryUiState
}

sealed interface IpoCalendarUiState {
    data object Loading : IpoCalendarUiState
    data class Success(val events: List<IpoCalendarEvent>) : IpoCalendarUiState
    data object Empty : IpoCalendarUiState
    data class Error(val message: String) : IpoCalendarUiState
}

sealed interface IpoPerformanceUiState {
    data object Loading : IpoPerformanceUiState
    data class Success(val summary: IpoPerformanceSummary) : IpoPerformanceUiState
    data object Empty : IpoPerformanceUiState
    data class Error(val message: String) : IpoPerformanceUiState
}
