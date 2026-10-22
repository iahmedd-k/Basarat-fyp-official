package com.fyp.basarattradeinvest.feature.etf

import com.fyp.basarattradeinvest.domain.model.etf.EtfItem

sealed interface EtfDirectoryUiState {
    data object Loading : EtfDirectoryUiState
    data class Success(
        val total: Int,
        val shariahCount: Int,
        val conventionalCount: Int,
        val etfs: List<EtfItem>
    ) : EtfDirectoryUiState
    data object Empty : EtfDirectoryUiState
    data class Error(val message: String) : EtfDirectoryUiState
}
