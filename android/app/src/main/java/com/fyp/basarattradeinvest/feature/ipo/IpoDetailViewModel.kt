package com.fyp.basarattradeinvest.feature.ipo

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.domain.repository.IpoRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class IpoDetailViewModel(
    private val repository: IpoRepository = NetworkClient.ipoRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<IpoDetailUiState>(IpoDetailUiState.Loading)
    val uiState: StateFlow<IpoDetailUiState> = _uiState.asStateFlow()

    private var loadedSymbol: String? = null

    fun ensureLoaded(symbol: String) {
        if (loadedSymbol == symbol && _uiState.value is IpoDetailUiState.Success) return
        load(symbol)
    }

    fun load(symbol: String) {
        loadedSymbol = symbol
        viewModelScope.launch {
            _uiState.value = IpoDetailUiState.Loading
            repository.getIpoDetail(symbol).fold(
                onSuccess = { ipo -> _uiState.value = IpoDetailUiState.Success(ipo) },
                onFailure = { error ->
                    _uiState.value = IpoDetailUiState.Error(error.message ?: "Unable to load IPO details.")
                }
            )
        }
    }
}
