package com.fyp.basarattradeinvest.feature.ipo

import com.fyp.basarattradeinvest.domain.model.ipo.IpoItem

sealed interface IpoDetailUiState {
    data object Loading : IpoDetailUiState
    data class Success(val ipo: IpoItem) : IpoDetailUiState
    data class Error(val message: String) : IpoDetailUiState
}
