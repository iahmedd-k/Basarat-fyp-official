package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloJob
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloResult
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.risk.StressTestResult

interface RiskRepository {
    suspend fun getValueAtRisk(confidence: Int? = null, horizon: String? = null): Result<PortfolioVaR>
    suspend fun startMonteCarloSimulation(numSimulations: Int, horizonDays: Int): Result<MonteCarloJob>
    suspend fun getMonteCarloResult(taskId: String): Result<MonteCarloResult>
    suspend fun getStressTest(scenario: String? = null): Result<StressTestResult>
}
