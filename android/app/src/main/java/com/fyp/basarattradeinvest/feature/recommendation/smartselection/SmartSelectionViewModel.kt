package com.fyp.basarattradeinvest.feature.recommendation.smartselection

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.RecommendationsRepositoryImpl
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository
import com.fyp.basarattradeinvest.domain.repository.StockRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.util.Locale

class SmartSelectionViewModel(
    private val recommendationsRepository: RecommendationsRepository = RecommendationsRepositoryImpl(),
    private val stockRepository: StockRepository = StockRepositoryImpl()
) : ViewModel() {

    private val _uiState = MutableStateFlow(SmartSelectionUiState())
    val uiState: StateFlow<SmartSelectionUiState> = _uiState.asStateFlow()

    private val setupCache = mutableMapOf<String, CachedSetup>()
    private var setupJob: kotlinx.coroutines.Job? = null

    init {
        loadCandidates()
    }

    fun loadCandidates() {
        viewModelScope.launch {
            val current = _uiState.value
            _uiState.value = current.copy(isLoadingCandidates = true, candidatesError = null)

            val result = recommendationsRepository.getLiveRecommendations(limit = 20)
            if (result.isFailure) {
                _uiState.value = _uiState.value.copy(
                    isLoadingCandidates = false,
                    candidatesError = result.exceptionOrNull()?.message
                        ?: "Unable to load smart selections."
                )
                return@launch
            }

            val candidates = result.getOrThrow()
            val selected = candidates.firstOrNull { it.symbol == current.selectedSymbol }
                ?: candidates.firstOrNull()
            _uiState.value = _uiState.value.copy(
                isLoadingCandidates = false,
                candidates = candidates,
                candidatesError = null,
                selectedSymbol = selected?.symbol,
                selectedSetup = null,
                setupMessage = null
            )

            if (selected != null) selectStock(selected.symbol)
        }
    }

    fun selectStock(symbol: String) {
        val normalizedSymbol = symbol.trim().uppercase(Locale.ROOT)
        val current = _uiState.value
        val recommendation = current.candidates.firstOrNull { it.symbol == normalizedSymbol } ?: return
        if (current.selectedSymbol == normalizedSymbol && current.selectedSetup != null) return

        setupJob?.cancel()
        val cached = setupCache[normalizedSymbol]?.takeIf {
            System.currentTimeMillis() - it.savedAt < SETUP_CACHE_TTL_MS
        }?.setup
        _uiState.value = current.copy(
            selectedSymbol = normalizedSymbol,
            selectedSetup = cached,
            isLoadingSetup = cached == null,
            setupMessage = null
        )
        if (cached != null) return

        setupJob = viewModelScope.launch {
            try {
                val (targetStopResult, historyResult) = coroutineScope {
                    val targetStop = async {
                        recommendationsRepository.getLiveTargetStop(normalizedSymbol)
                    }
                    val history = async {
                        stockRepository.getPriceHistory(normalizedSymbol, "1M")
                    }
                    targetStop.await() to history.await()
                }

                val targetStop = targetStopResult.getOrNull()
                val candles = historyResult.getOrDefault(emptyList())
                val target = targetStop?.targetPrice?.takeIf { it > 0.0 }
                    ?: recommendation.targetPrice?.takeIf { it > 0.0 }
                val stop = targetStop?.stopLoss?.takeIf { it > 0.0 }
                    ?: recommendation.stopLoss?.takeIf { it > 0.0 }
                val price = targetStop?.currentPrice?.takeIf { it > 0.0 }
                    ?: recommendation.currentPrice?.takeIf { it > 0.0 }
                    ?: candles.lastOrNull()?.close?.toDouble()?.takeIf { it > 0.0 }

                val setup = SmartSelectionSetup(
                    recommendation = recommendation,
                    candles = candles,
                    targetStop = targetStop,
                    currentPrice = price,
                    targetPrice = target,
                    stopLoss = stop,
                    breakout = buildBreakout(candles)
                )
                setupCache[normalizedSymbol] = CachedSetup(setup, System.currentTimeMillis())

                val setupMessage = when {
                    candles.isEmpty() && (target == null || stop == null) ->
                        "Price history and live target/stop levels are unavailable for this stock."
                    candles.isEmpty() ->
                        "Price history is temporarily unavailable. Live target and stop levels are shown below."
                    target == null || stop == null ->
                        "The backend did not provide both live target and stop levels for this stock."
                    else -> null
                }

                if (_uiState.value.selectedSymbol == normalizedSymbol) {
                    _uiState.value = _uiState.value.copy(
                        isLoadingSetup = false,
                        selectedSetup = setup,
                        setupMessage = setupMessage
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (_uiState.value.selectedSymbol == normalizedSymbol) {
                    _uiState.value = _uiState.value.copy(
                        isLoadingSetup = false,
                        selectedSetup = null,
                        setupMessage = error.message ?: "Unable to load this stock's setup."
                    )
                }
            }
        }
    }

    fun retry() {
        setupCache.clear()
        loadCandidates()
    }

    private fun buildBreakout(candles: List<CandleEntry>): BreakoutLevels? {
        if (candles.size < MIN_BREAKOUT_BARS) return null
        val last = candles.last()
        val prior = candles.dropLast(1)
        val resistance = prior.maxOf { it.high.toDouble() }
        val support = prior.minOf { it.low.toDouble() }
        val lastClose = last.close.toDouble()
        if (resistance <= 0.0 || support <= 0.0 || lastClose <= 0.0) return null

        val averageVolume = prior.map { it.volume.toDouble() }.average()
        val volumeRatio = if (averageVolume > 0.0) last.volume / averageVolume else 0.0

        return BreakoutLevels(
            resistance = resistance,
            support = support,
            lastClose = lastClose,
            distanceToBreakoutPct = ((resistance - lastClose) / lastClose) * 100.0,
            volumeRatio = volumeRatio,
            isConfirmed = lastClose > resistance && volumeRatio >= VOLUME_CONFIRMATION_RATIO
        )
    }

    private data class CachedSetup(
        val setup: SmartSelectionSetup,
        val savedAt: Long
    )

    private companion object {
        const val SETUP_CACHE_TTL_MS = 3 * 60 * 1000L
        const val MIN_BREAKOUT_BARS = 5
        const val VOLUME_CONFIRMATION_RATIO = 1.5
    }
}
