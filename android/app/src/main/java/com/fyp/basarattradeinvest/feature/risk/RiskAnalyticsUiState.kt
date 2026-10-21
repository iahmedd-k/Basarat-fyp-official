package com.fyp.basarattradeinvest.feature.risk

import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloResult
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.risk.StressTestResult

sealed interface VaRUiState {
    data object Loading : VaRUiState
    data class Success(val data: PortfolioVaR) : VaRUiState
    data class Error(val message: String) : VaRUiState
}

sealed interface MonteCarloUiState {
    data object Idle : MonteCarloUiState
    data object Starting : MonteCarloUiState
    data class Polling(val taskId: String, val attempts: Int) : MonteCarloUiState
    data class Success(val result: MonteCarloResult) : MonteCarloUiState
    data class Error(val message: String) : MonteCarloUiState
}

sealed interface StressTestUiState {
    data object Loading : StressTestUiState
    data class Success(val result: StressTestResult) : StressTestUiState
    data class Error(val message: String) : StressTestUiState
}

data class RiskAnalyticsUiState(
    val varState: VaRUiState = VaRUiState.Loading,
    val selectedConfidence: Int = 95,
    val selectedHorizon: String = "1D",
    val monteCarloState: MonteCarloUiState = MonteCarloUiState.Idle,
    val simulationsCount: Int = 1000,
    val horizonDays: Int = 30,
    val stressTestState: StressTestUiState = StressTestUiState.Loading,
    val selectedScenario: String = "2008_crash"
)
