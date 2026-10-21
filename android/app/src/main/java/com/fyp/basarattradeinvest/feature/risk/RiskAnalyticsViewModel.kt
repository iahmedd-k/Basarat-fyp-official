package com.fyp.basarattradeinvest.feature.risk

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.domain.usecase.risk.GetMonteCarloResultUseCase
import com.fyp.basarattradeinvest.domain.usecase.risk.GetPortfolioVaRUseCase
import com.fyp.basarattradeinvest.domain.usecase.risk.GetStressTestScenarioUseCase
import com.fyp.basarattradeinvest.domain.usecase.risk.StartMonteCarloSimulationUseCase
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class RiskAnalyticsViewModel(
    private val getPortfolioVaRUseCase: GetPortfolioVaRUseCase = GetPortfolioVaRUseCase(),
    private val startMonteCarloSimulationUseCase: StartMonteCarloSimulationUseCase = StartMonteCarloSimulationUseCase(),
    private val getMonteCarloResultUseCase: GetMonteCarloResultUseCase = GetMonteCarloResultUseCase(),
    private val getStressTestScenarioUseCase: GetStressTestScenarioUseCase = GetStressTestScenarioUseCase()
) : ViewModel() {

    private val _uiState = MutableStateFlow(RiskAnalyticsUiState())
    val uiState: StateFlow<RiskAnalyticsUiState> = _uiState.asStateFlow()

    private var pollingJob: Job? = null

    init {
        loadVaR()
        loadStressTest()
    }

    fun loadVaR(confidence: Int? = null, horizon: String? = null) {
        val conf = confidence ?: _uiState.value.selectedConfidence
        val horiz = horizon ?: _uiState.value.selectedHorizon

        _uiState.update {
            it.copy(
                varState = VaRUiState.Loading,
                selectedConfidence = conf,
                selectedHorizon = horiz
            )
        }

        viewModelScope.launch {
            val result = getPortfolioVaRUseCase(confidence = conf, horizon = horiz)
            result.fold(
                onSuccess = { vaR ->
                    _uiState.update { it.copy(varState = VaRUiState.Success(vaR)) }
                },
                onFailure = { error ->
                    _uiState.update {
                        it.copy(varState = VaRUiState.Error(error.localizedMessage ?: "Failed to calculate VaR"))
                    }
                }
            )
        }
    }

    fun startMonteCarlo(numSimulations: Int = _uiState.value.simulationsCount, horizonDays: Int = _uiState.value.horizonDays) {
        // Validate input ranges matching OpenAPI contract
        val validSimulations = numSimulations.coerceIn(100, 10000)
        val validHorizonDays = horizonDays.coerceIn(1, 365)

        pollingJob?.cancel()

        _uiState.update {
            it.copy(
                monteCarloState = MonteCarloUiState.Starting,
                simulationsCount = validSimulations,
                horizonDays = validHorizonDays
            )
        }

        pollingJob = viewModelScope.launch {
            val startResult = startMonteCarloSimulationUseCase(
                numSimulations = validSimulations,
                horizonDays = validHorizonDays
            )

            startResult.fold(
                onSuccess = { job ->
                    pollMonteCarloJob(job.jobId)
                },
                onFailure = { error ->
                    _uiState.update {
                        it.copy(monteCarloState = MonteCarloUiState.Error(error.localizedMessage ?: "Failed to start simulation"))
                    }
                }
            )
        }
    }

    private suspend fun pollMonteCarloJob(taskId: String) {
        val maxAttempts = 15
        val delayMillis = 2000L

        for (attempt in 1..maxAttempts) {
            _uiState.update {
                it.copy(monteCarloState = MonteCarloUiState.Polling(taskId = taskId, attempts = attempt))
            }

            val result = getMonteCarloResultUseCase(taskId)
            var isFinished = false

            result.fold(
                onSuccess = { mcResult ->
                    when (mcResult.status.lowercase()) {
                        "completed" -> {
                            _uiState.update { it.copy(monteCarloState = MonteCarloUiState.Success(mcResult)) }
                            isFinished = true
                        }
                        "failed" -> {
                            val msg = mcResult.error ?: "Monte Carlo simulation execution failed"
                            _uiState.update { it.copy(monteCarloState = MonteCarloUiState.Error(msg)) }
                            isFinished = true
                        }
                        else -> {
                            // Still pending or running, continue polling
                        }
                    }
                },
                onFailure = { error ->
                    // Transient polling error or fatal
                    if (attempt == maxAttempts) {
                        _uiState.update {
                            it.copy(monteCarloState = MonteCarloUiState.Error(error.localizedMessage ?: "Simulation poll failed"))
                        }
                        isFinished = true
                    }
                }
            )

            if (isFinished) return

            delay(delayMillis)
        }

        _uiState.update {
            it.copy(monteCarloState = MonteCarloUiState.Error("Simulation timed out. Please try again."))
        }
    }

    fun loadStressTest(scenario: String? = null) {
        val sc = scenario ?: _uiState.value.selectedScenario

        _uiState.update {
            it.copy(
                stressTestState = StressTestUiState.Loading,
                selectedScenario = sc
            )
        }

        viewModelScope.launch {
            val result = getStressTestScenarioUseCase(sc)
            result.fold(
                onSuccess = { stressTest ->
                    _uiState.update { it.copy(stressTestState = StressTestUiState.Success(stressTest)) }
                },
                onFailure = { error ->
                    _uiState.update {
                        it.copy(stressTestState = StressTestUiState.Error(error.localizedMessage ?: "Failed to load stress test"))
                    }
                }
            )
        }
    }

    override fun onCleared() {
        super.onCleared()
        pollingJob?.cancel()
    }
}
