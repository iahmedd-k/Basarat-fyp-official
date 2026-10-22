package com.fyp.basarattradeinvest.feature.ipo

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.domain.repository.IpoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Shared by the IPO tab host and its three child tab fragments. Each tab loads lazily on first
 * view and retains its state, so navigating away and back does not trigger a refetch.
 */
class IpoViewModel(
    private val repository: IpoRepository = NetworkClient.ipoRepository
) : ViewModel() {

    private val _directoryState = MutableStateFlow<IpoDirectoryUiState>(IpoDirectoryUiState.Loading)
    val directoryState: StateFlow<IpoDirectoryUiState> = _directoryState.asStateFlow()

    private val _calendarState = MutableStateFlow<IpoCalendarUiState>(IpoCalendarUiState.Loading)
    val calendarState: StateFlow<IpoCalendarUiState> = _calendarState.asStateFlow()

    private val _performanceState = MutableStateFlow<IpoPerformanceUiState>(IpoPerformanceUiState.Loading)
    val performanceState: StateFlow<IpoPerformanceUiState> = _performanceState.asStateFlow()

    private var directoryRequested = false
    private var calendarRequested = false
    private var performanceRequested = false

    fun ensureDirectoryLoaded() {
        if (directoryRequested) return
        directoryRequested = true
        loadDirectory()
    }

    fun ensureCalendarLoaded() {
        if (calendarRequested) return
        calendarRequested = true
        loadCalendar()
    }

    fun ensurePerformanceLoaded() {
        if (performanceRequested) return
        performanceRequested = true
        loadPerformance()
    }

    fun loadDirectory() {
        viewModelScope.launch {
            _directoryState.value = IpoDirectoryUiState.Loading
            repository.getIpos().fold(
                onSuccess = { items ->
                    _directoryState.value = if (items.isEmpty()) IpoDirectoryUiState.Empty
                    else IpoDirectoryUiState.Success(items)
                },
                onFailure = { error ->
                    _directoryState.value = IpoDirectoryUiState.Error(error.message ?: "Unable to load IPOs.")
                }
            )
        }
    }

    fun loadCalendar() {
        viewModelScope.launch {
            _calendarState.value = IpoCalendarUiState.Loading
            repository.getIpoCalendar().fold(
                onSuccess = { events ->
                    _calendarState.value = if (events.isEmpty()) IpoCalendarUiState.Empty
                    else IpoCalendarUiState.Success(events)
                },
                onFailure = { error ->
                    _calendarState.value = IpoCalendarUiState.Error(error.message ?: "Unable to load the IPO calendar.")
                }
            )
        }
    }

    fun loadPerformance() {
        viewModelScope.launch {
            _performanceState.value = IpoPerformanceUiState.Loading
            repository.getIpoPerformance().fold(
                onSuccess = { summary ->
                    _performanceState.value = if (summary.topPerformers.isEmpty() && summary.recentListings.isEmpty()) {
                        IpoPerformanceUiState.Empty
                    } else {
                        IpoPerformanceUiState.Success(summary)
                    }
                },
                onFailure = { error ->
                    _performanceState.value = IpoPerformanceUiState.Error(error.message ?: "Unable to load IPO performance.")
                }
            )
        }
    }
}
