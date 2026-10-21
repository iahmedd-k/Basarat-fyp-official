package com.fyp.basarattradeinvest.feature.shariah.details

import com.fyp.basarattradeinvest.domain.model.shariah.DividendPurificationResult
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCompliance
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCriteria

sealed interface StockShariahComplianceUiState {
    data object Loading : StockShariahComplianceUiState
    data class Success(val compliance: StockShariahCompliance) : StockShariahComplianceUiState
    data class Error(val message: String) : StockShariahComplianceUiState
}

sealed interface StockShariahCriteriaUiState {
    data object Loading : StockShariahCriteriaUiState
    data class Success(val criteria: StockShariahCriteria) : StockShariahCriteriaUiState
    data class Error(val message: String) : StockShariahCriteriaUiState
}

sealed interface PurificationCalculationUiState {
    data object Idle : PurificationCalculationUiState
    data object Calculating : PurificationCalculationUiState
    data class Success(val result: DividendPurificationResult) : PurificationCalculationUiState
    data class Error(val message: String) : PurificationCalculationUiState
}
