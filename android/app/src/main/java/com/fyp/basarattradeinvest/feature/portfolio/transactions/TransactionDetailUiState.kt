package com.fyp.basarattradeinvest.feature.portfolio.transactions

import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction

sealed interface TransactionDetailUiState {
    data object Loading : TransactionDetailUiState
    data class Success(val transaction: PortfolioTransaction) : TransactionDetailUiState
    data object Deleting : TransactionDetailUiState
    data object Deleted : TransactionDetailUiState
    data class Error(val message: String) : TransactionDetailUiState
}
