package com.fyp.basarattradeinvest.feature.etf

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.domain.repository.EtfRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class EtfDirectoryViewModel(
    private val repository: EtfRepository = NetworkClient.etfRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow<EtfDirectoryUiState>(EtfDirectoryUiState.Loading)
    val uiState: StateFlow<EtfDirectoryUiState> = _uiState.asStateFlow()

    private var requested = false

    fun ensureLoaded() {
        if (requested) return
        requested = true
        load()
    }

    fun load() {
        viewModelScope.launch {
            _uiState.value = EtfDirectoryUiState.Loading
            repository.getEtfs().fold(
                onSuccess = { result ->
                    _uiState.value = if (result.etfs.isEmpty()) EtfDirectoryUiState.Empty
                    else EtfDirectoryUiState.Success(
                        total = result.total,
                        shariahCount = result.shariahCount,
                        conventionalCount = result.conventionalCount,
                        etfs = result.etfs
                    )
                },
                onFailure = { error ->
                    _uiState.value = EtfDirectoryUiState.Error(error.message ?: "Unable to load ETFs.")
                }
            )
        }
    }
}
