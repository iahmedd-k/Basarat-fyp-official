package com.fyp.basarattradeinvest.feature.portfolio.holding

import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingDetail

sealed interface HoldingDetailUiState {
    data object Loading : HoldingDetailUiState
    data class Success(val detail: HoldingDetail) : HoldingDetailUiState
    data class Error(val message: String) : HoldingDetailUiState
}
