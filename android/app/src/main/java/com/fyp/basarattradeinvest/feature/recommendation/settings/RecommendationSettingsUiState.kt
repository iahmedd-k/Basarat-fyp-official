package com.fyp.basarattradeinvest.feature.recommendation.settings

import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights

sealed interface RecommendationSettingsUiState {
    data object Loading : RecommendationSettingsUiState
    data class Loaded(
        val weights: EngineWeights,
        val isSaving: Boolean = false,
        val saveMessage: String? = null
    ) : RecommendationSettingsUiState
    data class Error(val message: String) : RecommendationSettingsUiState
}
