package com.fyp.basarattradeinvest.domain.usecase.risk

import com.fyp.basarattradeinvest.data.repository.RiskRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloJob
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloResult
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.risk.StressTestResult
import com.fyp.basarattradeinvest.domain.repository.RiskRepository

class GetPortfolioVaRUseCase(
    private val repository: RiskRepository = RiskRepositoryImpl()
) {
    suspend operator fun invoke(confidence: Int? = null, horizon: String? = null): Result<PortfolioVaR> {
        return repository.getValueAtRisk(confidence = confidence, horizon = horizon)
    }
}

class StartMonteCarloSimulationUseCase(
    private val repository: RiskRepository = RiskRepositoryImpl()
) {
    suspend operator fun invoke(numSimulations: Int, horizonDays: Int): Result<MonteCarloJob> {
        return repository.startMonteCarloSimulation(numSimulations = numSimulations, horizonDays = horizonDays)
    }
}

class GetMonteCarloResultUseCase(
    private val repository: RiskRepository = RiskRepositoryImpl()
) {
    suspend operator fun invoke(taskId: String): Result<MonteCarloResult> {
        return repository.getMonteCarloResult(taskId = taskId)
    }
}

class GetStressTestScenarioUseCase(
    private val repository: RiskRepository = RiskRepositoryImpl()
) {
    suspend operator fun invoke(scenario: String? = null): Result<StressTestResult> {
        return repository.getStressTest(scenario = scenario)
    }
}
