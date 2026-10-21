package com.fyp.basarattradeinvest.feature.stock.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.StockRepository
import com.fyp.basarattradeinvest.domain.usecase.stocks.SearchStocksUseCase
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

@OptIn(FlowPreview::class)
class StockSearchViewModel(
    private val repository: StockRepository = StockRepositoryImpl(),
    private val searchStocksUseCase: SearchStocksUseCase = SearchStocksUseCase(repository)
) : ViewModel() {

    private val _uiState = MutableStateFlow<StockSearchUiState>(StockSearchUiState.Idle)
    val uiState: StateFlow<StockSearchUiState> = _uiState.asStateFlow()

    private val queryFlow = MutableStateFlow("")

    init {
        viewModelScope.launch {
            queryFlow
                .debounce(300)
                .distinctUntilChanged()
                .collectLatest { query ->
                    executeSearch(query)
                }
        }
    }

    fun onQueryChanged(newQuery: String) {
        queryFlow.value = newQuery
    }

    private suspend fun executeSearch(query: String) {
        val trimmed = query.trim()
        if (trimmed.isEmpty()) {
            _uiState.value = StockSearchUiState.Idle
            return
        }

        _uiState.value = StockSearchUiState.Loading

        val result = searchStocksUseCase(trimmed)
        if (result.isSuccess) {
            val list = result.getOrThrow()
            if (list.isEmpty()) {
                _uiState.value = StockSearchUiState.Empty(trimmed)
            } else {
                _uiState.value = StockSearchUiState.Success(list, trimmed)
            }
        } else {
            _uiState.value = StockSearchUiState.Error(
                result.exceptionOrNull()?.message ?: "Unable to load search results"
            )
        }
    }

    fun retry() {
        viewModelScope.launch {
            executeSearch(queryFlow.value)
        }
    }
}
