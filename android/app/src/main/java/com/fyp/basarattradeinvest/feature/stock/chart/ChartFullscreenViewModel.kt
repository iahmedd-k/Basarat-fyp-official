package com.fyp.basarattradeinvest.feature.stock.chart

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.StockRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ChartFullscreenViewModel(
    private val repository: StockRepository = StockRepositoryImpl()
) : ViewModel() {

    private val _uiState = MutableStateFlow<ChartFullscreenUiState>(ChartFullscreenUiState.Loading)
    val uiState: StateFlow<ChartFullscreenUiState> = _uiState.asStateFlow()

    private var currentSymbol: String = "LUCK"
    private var currentTimeframe: String = "1W"
    private val activeIndicators = mutableSetOf("MA", "VOL")
    private var currentTool: DrawingTool = DrawingTool.CROSSHAIR
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L

    fun ensureLoaded(symbol: String, timeframe: String = currentTimeframe) {
        val state = _uiState.value
        val isSameChart = currentSymbol == symbol && currentTimeframe == timeframe && state is ChartFullscreenUiState.Success
        val shouldLoad = !isSameChart || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
        if (shouldLoad) {
            loadChart(symbol, timeframe)
        }
    }

    fun loadChart(symbol: String, timeframe: String = currentTimeframe) {
        currentSymbol = symbol
        currentTimeframe = timeframe

        viewModelScope.launch {
            val currentState = _uiState.value
            // Compare against what the cached state actually shows. This VM is activity-scoped,
            // so a previous symbol/timeframe's Success must not skip this load (also fixes
            // timeframe switches being ignored inside the freshness window).
            val isSameChart = currentState is ChartFullscreenUiState.Success &&
                currentState.stockDetail.symbol.equals(symbol, ignoreCase = true) &&
                currentState.selectedTimeframe == timeframe
            if (isSameChart && System.currentTimeMillis() - lastSuccessfulFetchAt <= freshnessWindowMs) {
                return@launch
            }
            _uiState.value = ChartFullscreenUiState.Loading

            val detailResult = repository.getStockDetail(currentSymbol)
            val chartResult = repository.getChartData(currentSymbol, currentTimeframe)

            if (detailResult.isSuccess && chartResult.isSuccess) {
                val detail = detailResult.getOrThrow()
                val candles = chartResult.getOrDefault(emptyList())

                if (candles.isEmpty()) {
                    lastSuccessfulFetchAt = System.currentTimeMillis()
                    _uiState.value = ChartFullscreenUiState.Empty
                } else {
                    lastSuccessfulFetchAt = System.currentTimeMillis()
                    _uiState.value = ChartFullscreenUiState.Success(
                        stockDetail = detail,
                        candles = candles,
                        selectedTimeframe = currentTimeframe,
                        activeIndicators = activeIndicators.toSet(),
                        selectedTool = currentTool
                    )
                }
            } else {
                _uiState.value = ChartFullscreenUiState.Error("Unable to load chart data for $symbol")
            }
        }
    }

    fun setTimeframe(timeframe: String) {
        if (currentTimeframe == timeframe) return
        currentTimeframe = timeframe
        loadChart(currentSymbol, timeframe)
    }

    fun toggleIndicator(indicator: String) {
        if (activeIndicators.contains(indicator)) {
            activeIndicators.remove(indicator)
        } else {
            activeIndicators.add(indicator)
        }

        val currentState = _uiState.value
        if (currentState is ChartFullscreenUiState.Success) {
            _uiState.value = currentState.copy(
                activeIndicators = activeIndicators.toSet()
            )
        }
    }

    fun selectTool(tool: DrawingTool) {
        currentTool = if (currentTool == tool) DrawingTool.NONE else tool
        val currentState = _uiState.value
        if (currentState is ChartFullscreenUiState.Success) {
            _uiState.value = currentState.copy(selectedTool = currentTool)
        }
    }

    fun clearDrawings() {
        currentTool = DrawingTool.NONE
        val currentState = _uiState.value
        if (currentState is ChartFullscreenUiState.Success) {
            _uiState.value = currentState.copy(selectedTool = currentTool)
        }
    }

    fun retry() {
        loadChart(currentSymbol, currentTimeframe)
    }
}
