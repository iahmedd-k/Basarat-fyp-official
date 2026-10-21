package com.fyp.basarattradeinvest.feature.shariah.details

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.ShariahRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.shariah.CalculateDividendPurificationUseCase
import com.fyp.basarattradeinvest.domain.usecase.shariah.GetStockShariahCriteriaUseCase
import com.fyp.basarattradeinvest.domain.usecase.shariah.GetStockShariahScreeningUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class StockShariahDetailsViewModel(
    private val getComplianceUseCase: GetStockShariahScreeningUseCase = GetStockShariahScreeningUseCase(ShariahRepositoryImpl()),
    private val getCriteriaUseCase: GetStockShariahCriteriaUseCase = GetStockShariahCriteriaUseCase(ShariahRepositoryImpl()),
    private val calculatePurificationUseCase: CalculateDividendPurificationUseCase = CalculateDividendPurificationUseCase(ShariahRepositoryImpl())
) : ViewModel() {

    private val _complianceState = MutableStateFlow<StockShariahComplianceUiState>(StockShariahComplianceUiState.Loading)
    val complianceState: StateFlow<StockShariahComplianceUiState> = _complianceState.asStateFlow()

    private val _criteriaState = MutableStateFlow<StockShariahCriteriaUiState>(StockShariahCriteriaUiState.Loading)
    val criteriaState: StateFlow<StockShariahCriteriaUiState> = _criteriaState.asStateFlow()

    private val _purificationState = MutableStateFlow<PurificationCalculationUiState>(PurificationCalculationUiState.Idle)
    val purificationState: StateFlow<PurificationCalculationUiState> = _purificationState.asStateFlow()

    fun loadStockShariah(symbol: String) {
        loadCompliance(symbol)
        loadCriteria(symbol)
    }

    fun loadCompliance(symbol: String) {
        viewModelScope.launch {
            _complianceState.value = StockShariahComplianceUiState.Loading
            val result = getComplianceUseCase(symbol)
            result.fold(
                onSuccess = { compliance ->
                    _complianceState.value = StockShariahComplianceUiState.Success(compliance)
                },
                onFailure = { error ->
                    _complianceState.value = StockShariahComplianceUiState.Error(
                        error.message ?: "Unable to load Shariah compliance for $symbol"
                    )
                }
            )
        }
    }

    fun loadCriteria(symbol: String) {
        viewModelScope.launch {
            _criteriaState.value = StockShariahCriteriaUiState.Loading
            val result = getCriteriaUseCase(symbol)
            result.fold(
                onSuccess = { criteria ->
                    _criteriaState.value = StockShariahCriteriaUiState.Success(criteria)
                },
                onFailure = { error ->
                    _criteriaState.value = StockShariahCriteriaUiState.Error(
                        error.message ?: "Unable to load screening criteria for $symbol"
                    )
                }
            )
        }
    }

    fun calculatePurification(symbol: String, dividendIncome: Double) {
        viewModelScope.launch {
            _purificationState.value = PurificationCalculationUiState.Calculating
            val result = calculatePurificationUseCase(symbol, dividendIncome)
            result.fold(
                onSuccess = { res ->
                    _purificationState.value = PurificationCalculationUiState.Success(res)
                },
                onFailure = { error ->
                    _purificationState.value = PurificationCalculationUiState.Error(
                        error.message ?: "Failed to calculate purification amount."
                    )
                }
            )
        }
    }
}
