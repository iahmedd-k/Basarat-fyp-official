package com.fyp.basarattradeinvest.feature.portfolio.transactions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.PortfolioRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.PortfolioRepository
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetTransactionsUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class TransactionHistoryViewModel(
    private val getTransactionsUseCase: GetTransactionsUseCase
) : ViewModel() {

    constructor() : this(PortfolioRepositoryImpl())

    constructor(repository: PortfolioRepository) : this(
        GetTransactionsUseCase(repository)
    )

    class Factory(
        private val repository: PortfolioRepository = PortfolioRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(TransactionHistoryViewModel::class.java)) {
                return TransactionHistoryViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }

    private val _uiState = MutableStateFlow<TransactionHistoryUiState>(TransactionHistoryUiState.Loading)
    val uiState: StateFlow<TransactionHistoryUiState> = _uiState.asStateFlow()

    private var currentTypeFilter: String? = null // null: ALL, "BUY", "SELL"
    private var currentPage: Int = 1

    init {
        loadTransactions()
    }

    fun setFilterType(type: String?) {
        if (currentTypeFilter == type) return
        currentTypeFilter = type
        currentPage = 1
        loadTransactions()
    }

    fun loadTransactions() {
        viewModelScope.launch {
            _uiState.value = TransactionHistoryUiState.Loading
            val result = getTransactionsUseCase(
                page = currentPage,
                limit = 50,
                transactionType = currentTypeFilter
            )
            if (result.isSuccess) {
                val page = result.getOrThrow()
                if (page.items.isEmpty()) {
                    _uiState.value = TransactionHistoryUiState.Empty
                } else {
                    _uiState.value = TransactionHistoryUiState.Success(page)
                }
            } else {
                _uiState.value = TransactionHistoryUiState.Error(
                    result.exceptionOrNull()?.message ?: "Unable to load transactions."
                )
            }
        }
    }
}
