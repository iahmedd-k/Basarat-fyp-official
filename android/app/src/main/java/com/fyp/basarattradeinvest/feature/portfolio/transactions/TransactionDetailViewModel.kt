package com.fyp.basarattradeinvest.feature.portfolio.transactions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.PortfolioRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.PortfolioRepository
import com.fyp.basarattradeinvest.domain.usecase.portfolio.DeleteTransactionUseCase
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetTransactionDetailUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class TransactionDetailViewModel(
    private val getDetailUseCase: GetTransactionDetailUseCase,
    private val deleteUseCase: DeleteTransactionUseCase
) : ViewModel() {

    constructor() : this(PortfolioRepositoryImpl())

    constructor(repository: PortfolioRepository) : this(
        getDetailUseCase = GetTransactionDetailUseCase(repository),
        deleteUseCase = DeleteTransactionUseCase(repository)
    )

    class Factory(
        private val repository: PortfolioRepository = PortfolioRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(TransactionDetailViewModel::class.java)) {
                return TransactionDetailViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }

    private val _uiState = MutableStateFlow<TransactionDetailUiState>(TransactionDetailUiState.Loading)
    val uiState: StateFlow<TransactionDetailUiState> = _uiState.asStateFlow()

    fun loadTransaction(transactionId: String) {
        viewModelScope.launch {
            _uiState.value = TransactionDetailUiState.Loading
            val result = getDetailUseCase(transactionId)
            if (result.isSuccess) {
                _uiState.value = TransactionDetailUiState.Success(result.getOrThrow())
            } else {
                _uiState.value = TransactionDetailUiState.Error(
                    result.exceptionOrNull()?.message ?: "Unable to load transaction details."
                )
            }
        }
    }

    fun deleteTransaction(transactionId: String) {
        if (_uiState.value is TransactionDetailUiState.Deleting) return
        viewModelScope.launch {
            _uiState.value = TransactionDetailUiState.Deleting
            val result = deleteUseCase(transactionId)
            if (result.isSuccess) {
                _uiState.value = TransactionDetailUiState.Deleted
            } else {
                _uiState.value = TransactionDetailUiState.Error(
                    result.exceptionOrNull()?.message ?: "Failed to delete transaction."
                )
            }
        }
    }
}
