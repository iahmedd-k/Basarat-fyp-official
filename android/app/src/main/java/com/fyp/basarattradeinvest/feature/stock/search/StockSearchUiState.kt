package com.fyp.basarattradeinvest.feature.stock.search

import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult

sealed interface StockSearchUiState {
    data object Idle : StockSearchUiState
    data object Loading : StockSearchUiState
    data class Success(val results: List<StockSearchResult>, val query: String) : StockSearchUiState
    data class Empty(val query: String) : StockSearchUiState
    data class Error(val message: String) : StockSearchUiState
}
