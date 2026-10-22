package com.fyp.basarattradeinvest.feature.recommendation.list

import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation

sealed interface RecommendationsUiState {
    data object Loading : RecommendationsUiState
    data class Success(
        val recommendations: List<StockRecommendation>,
        val selectedRiskProfile: String,
        val selectedSector: String?
    ) : RecommendationsUiState
    data class Empty(
        val selectedRiskProfile: String
    ) : RecommendationsUiState
    data class Error(
        val message: String
    ) : RecommendationsUiState
}
