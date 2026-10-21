package com.fyp.basarattradeinvest.feature.portfolio.transactions

import com.fyp.basarattradeinvest.domain.model.portfolio.TransactionListPage

sealed interface TransactionHistoryUiState {
    data object Loading : TransactionHistoryUiState
    data class Success(val page: TransactionListPage) : TransactionHistoryUiState
    data object Empty : TransactionHistoryUiState
    data class Error(val message: String) : TransactionHistoryUiState
}
