package com.fyp.basarattradeinvest.feature.recommendation.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.RecommendationsRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository
import com.fyp.basarattradeinvest.domain.usecase.recommendations.GetEngineWeightsUseCase
import com.fyp.basarattradeinvest.domain.usecase.recommendations.SetEngineWeightsUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class RecommendationSettingsViewModel(
    private val repository: RecommendationsRepository = RecommendationsRepositoryImpl(),
    private val getEngineWeightsUseCase: GetEngineWeightsUseCase = GetEngineWeightsUseCase(repository),
    private val setEngineWeightsUseCase: SetEngineWeightsUseCase = SetEngineWeightsUseCase(repository)
) : ViewModel() {

    private val _uiState = MutableStateFlow<RecommendationSettingsUiState>(RecommendationSettingsUiState.Loading)
    val uiState: StateFlow<RecommendationSettingsUiState> = _uiState.asStateFlow()

    init {
        loadWeights()
    }

    fun loadWeights() {
        viewModelScope.launch {
            _uiState.value = RecommendationSettingsUiState.Loading
            val result = getEngineWeightsUseCase()
            if (result.isSuccess) {
                _uiState.value = RecommendationSettingsUiState.Loaded(result.getOrThrow())
            } else {
                _uiState.value = RecommendationSettingsUiState.Error(
                    result.exceptionOrNull()?.message ?: "Unable to load engine weights"
                )
            }
        }
    }

    fun saveWeights(gru: Double, tech: Double, fund: Double) {
        val currentState = _uiState.value
        val currentWeights = if (currentState is RecommendationSettingsUiState.Loaded) {
            currentState.weights
        } else {
            EngineWeights(0.33, 0.33, 0.34)
        }

        viewModelScope.launch {
            _uiState.value = RecommendationSettingsUiState.Loaded(
                weights = currentWeights,
                isSaving = true
            )

            val result = setEngineWeightsUseCase(gru, tech, fund)
            if (result.isSuccess) {
                _uiState.value = RecommendationSettingsUiState.Loaded(
                    weights = result.getOrThrow(),
                    isSaving = false,
                    saveMessage = "Engine weights updated successfully"
                )
            } else {
                _uiState.value = RecommendationSettingsUiState.Loaded(
                    weights = currentWeights,
                    isSaving = false,
                    saveMessage = "Failed: ${result.exceptionOrNull()?.message ?: "Check permission or weight values"}"
                )
            }
        }
    }

    fun resetToDefaults() {
        saveWeights(0.33, 0.33, 0.34)
    }
}
