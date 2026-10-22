package com.fyp.basarattradeinvest.feature.recommendation.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.RecommendationsRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository
import com.fyp.basarattradeinvest.domain.usecase.recommendations.GetRecommendationDetailUseCase
import com.fyp.basarattradeinvest.domain.usecase.recommendations.GetTargetStopUseCase
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class StockRecommendationDetailViewModel(
    private val repository: RecommendationsRepository = RecommendationsRepositoryImpl(),
    private val getRecommendationDetailUseCase: GetRecommendationDetailUseCase = GetRecommendationDetailUseCase(repository),
    private val getTargetStopUseCase: GetTargetStopUseCase = GetTargetStopUseCase(repository)
) : ViewModel() {

    private val _uiState = MutableStateFlow<StockRecommendationDetailUiState>(StockRecommendationDetailUiState.Loading)
    val uiState: StateFlow<StockRecommendationDetailUiState> = _uiState.asStateFlow()

    private var currentSymbol: String = ""
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L

    fun ensureLoaded(symbol: String) {
        val state = _uiState.value
        val isSameSymbol = currentSymbol == symbol && state is StockRecommendationDetailUiState.Success
        val shouldLoad = !isSameSymbol || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
        if (shouldLoad) {
            loadRecommendation(symbol)
        }
    }

    fun loadRecommendation(symbol: String, forceRefresh: Boolean = false) {
        currentSymbol = symbol
        viewModelScope.launch {
            val currentState = _uiState.value
            // Compare against the symbol the cached state actually holds; this VM is
            // activity-scoped, so a previous symbol's Success must not skip this load.
            val isSameSymbol = currentState is StockRecommendationDetailUiState.Success &&
                currentState.detail.symbol.equals(symbol, ignoreCase = true)
            if (!forceRefresh && isSameSymbol && System.currentTimeMillis() - lastSuccessfulFetchAt <= freshnessWindowMs) {
                return@launch
            }
            _uiState.value = StockRecommendationDetailUiState.Loading

            coroutineScope {
                val detailDeferred = async { getRecommendationDetailUseCase(symbol) }
                val targetStopDeferred = async { getTargetStopUseCase(symbol) }

                val detailResult = detailDeferred.await()
                val targetStopResult = targetStopDeferred.await()

                if (detailResult.isSuccess) {
                    lastSuccessfulFetchAt = System.currentTimeMillis()
                    _uiState.value = StockRecommendationDetailUiState.Success(
                        detail = detailResult.getOrThrow(),
                        targetStop = targetStopResult.getOrNull()
                    )
                } else {
                    _uiState.value = StockRecommendationDetailUiState.Error(
                        detailResult.exceptionOrNull()?.message ?: "Unable to load recommendation for $symbol"
                    )
                }
            }
        }
    }

    fun retry() {
        if (currentSymbol.isNotEmpty()) {
            loadRecommendation(currentSymbol)
        }
    }
}
