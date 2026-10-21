package com.fyp.basarattradeinvest.feature.portfolio.holding

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.PortfolioRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.PortfolioRepository
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetHoldingDetailUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class HoldingDetailViewModel(
    private val getHoldingDetailUseCase: GetHoldingDetailUseCase
) : ViewModel() {

    constructor() : this(PortfolioRepositoryImpl())

    constructor(repository: PortfolioRepository) : this(
        GetHoldingDetailUseCase(repository)
    )

    class Factory(
        private val repository: PortfolioRepository = PortfolioRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(HoldingDetailViewModel::class.java)) {
                return HoldingDetailViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }

    private val _uiState = MutableStateFlow<HoldingDetailUiState>(HoldingDetailUiState.Loading)
    val uiState: StateFlow<HoldingDetailUiState> = _uiState.asStateFlow()

    private var lastLoadedSymbol: String? = null
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L

    fun shouldLoadHolding(symbol: String): Boolean {
        val state = _uiState.value
        val isSameSymbol = lastLoadedSymbol == symbol && state is HoldingDetailUiState.Success
        return !isSameSymbol || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
    }

    fun loadHolding(symbol: String, forceRefresh: Boolean = false) {
        if (!forceRefresh && !shouldLoadHolding(symbol)) {
            return
        }

        lastLoadedSymbol = symbol

        viewModelScope.launch {
            _uiState.value = HoldingDetailUiState.Loading
            val result = getHoldingDetailUseCase(symbol)
            if (result.isSuccess) {
                lastSuccessfulFetchAt = System.currentTimeMillis()
                _uiState.value = HoldingDetailUiState.Success(result.getOrThrow())
            } else {
                _uiState.value = HoldingDetailUiState.Error(
                    result.exceptionOrNull()?.message ?: "Unable to load holding details."
                )
            }
        }
    }
}
