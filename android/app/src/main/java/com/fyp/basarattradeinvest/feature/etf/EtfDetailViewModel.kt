package com.fyp.basarattradeinvest.feature.etf

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.domain.repository.EtfRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class EtfDetailViewModel(
    private val repository: EtfRepository = NetworkClient.etfRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<EtfDetailUiState>(EtfDetailUiState.Loading)
    val uiState: StateFlow<EtfDetailUiState> = _uiState.asStateFlow()

    private var currentSymbol: String? = null
    private var historyRequested = false
    private var performanceRequested = false

    fun ensureLoaded(symbol: String) {
        if (currentSymbol == symbol && _uiState.value is EtfDetailUiState.Success) return
        loadDetail(symbol)
    }

    fun loadDetail(symbol: String) {
        currentSymbol = symbol
        historyRequested = false
        performanceRequested = false
        viewModelScope.launch {
            _uiState.value = EtfDetailUiState.Loading
            repository.getEtfDetail(symbol).fold(
                onSuccess = { etf -> _uiState.value = EtfDetailUiState.Success(etf = etf) },
                onFailure = { error ->
                    _uiState.value = EtfDetailUiState.Error(error.message ?: "Unable to load ETF details.")
                }
            )
        }
    }

    fun selectTab(tab: EtfDetailTab) {
        val state = _uiState.value as? EtfDetailUiState.Success ?: return
        if (state.selectedTab != tab) {
            _uiState.value = state.copy(selectedTab = tab)
        }
        when (tab) {
            EtfDetailTab.HISTORY -> if (!historyRequested) loadHistory()
            EtfDetailTab.PERFORMANCE -> if (!performanceRequested) loadPerformance()
            EtfDetailTab.OVERVIEW -> Unit
        }
    }

    fun selectTimeframe(timeframe: String) {
        val state = _uiState.value as? EtfDetailUiState.Success ?: return
        if (state.selectedTimeframe == timeframe) return
        _uiState.value = state.copy(selectedTimeframe = timeframe, historyState = EtfHistoryUiState.Loading)
        historyRequested = true
        fetchHistory(timeframe)
    }

    fun loadHistory() {
        val state = _uiState.value as? EtfDetailUiState.Success ?: return
        historyRequested = true
        updateHistory(EtfHistoryUiState.Loading)
        fetchHistory(state.selectedTimeframe)
    }

    fun retryHistory() {
        historyRequested = true
        loadHistory()
    }

    private fun fetchHistory(timeframe: String) {
        val symbol = currentSymbol ?: return
        viewModelScope.launch {
            repository.getEtfHistory(symbol, timeframe).fold(
                onSuccess = { entries ->
                    updateHistory(
                        if (entries.isEmpty()) EtfHistoryUiState.Empty
                        else EtfHistoryUiState.Success(entries)
                    )
                },
                onFailure = { error ->
                    updateHistory(EtfHistoryUiState.Error(error.message ?: "Unable to load price history."))
                }
            )
        }
    }

    fun loadPerformance() {
        performanceRequested = true
        updatePerformance(EtfPerformanceUiState.Loading)
        fetchPerformance()
    }

    fun retryPerformance() {
        performanceRequested = true
        loadPerformance()
    }

    private fun fetchPerformance() {
        val symbol = currentSymbol ?: return
        viewModelScope.launch {
            repository.getEtfPerformance(symbol).fold(
                onSuccess = { performance -> updatePerformance(EtfPerformanceUiState.Success(performance)) },
                onFailure = { error ->
                    updatePerformance(EtfPerformanceUiState.Error(error.message ?: "Unable to load performance."))
                }
            )
        }
    }

    private fun updateHistory(historyState: EtfHistoryUiState) {
        val state = _uiState.value as? EtfDetailUiState.Success ?: return
        _uiState.value = state.copy(historyState = historyState)
    }

    private fun updatePerformance(performanceState: EtfPerformanceUiState) {
        val state = _uiState.value as? EtfDetailUiState.Success ?: return
        _uiState.value = state.copy(performanceState = performanceState)
    }
}
