package com.fyp.basarattradeinvest.feature.recommendation.detail

import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationDetail
import com.fyp.basarattradeinvest.domain.model.recommendations.TargetStop

sealed interface StockRecommendationDetailUiState {
    data object Loading : StockRecommendationDetailUiState
    data class Success(
        val detail: RecommendationDetail,
        val targetStop: TargetStop?
    ) : StockRecommendationDetailUiState
    data class Error(val message: String) : StockRecommendationDetailUiState
}
