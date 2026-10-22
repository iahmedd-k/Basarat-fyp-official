package com.fyp.basarattradeinvest.domain.model.risk

data class PortfolioVaR(
    val confidence: Int,
    val horizon: String,
    val varValue: Double,
    val cvarValue: Double,
    val method: String,
    val numObservations: Int,
    val annualizedVolatility: Double
)

data class MonteCarloJob(
    val jobId: String,
    val status: String,
    val numSimulations: Int?,
    val horizonDays: Int?,
    val message: String?
)

data class PercentileEntry(
    val percentile: String,
    val value: Double
)

data class MonteCarloStats(
    val meanReturn: Double?,
    val stdReturn: Double?,
    val probLoss: Double?,
    val maxDrawdown: Double?,
    val bestCase: Double?
)

data class MonteCarloResult(
    val jobId: String,
    val status: String,
    val numSimulations: Int,
    val horizonDays: Int,
    val params: Map<String, Any>,
    val percentiles: List<PercentileEntry>,
    val stats: MonteCarloStats,
    val pathsSample: List<List<Double>>,
    val error: String?,
    val completedAt: String?
)

data class HoldingImpact(
    val symbol: String,
    val name: String? = null,
    val impactPct: Double? = null,
    val impactValue: Double? = null,
    val currentValue: Double? = null,
    val stressedValue: Double? = null
)

data class StressTestResult(
    val scenario: String,
    val name: String,
    val description: String,
    val portfolioImpact: Double,
    val portfolioImpactValue: Double,
    val worstCaseLoss: Double,
    val volatilityMultiplier: Double,
    val recoveryDays: Int,
    val currentValue: Double,
    val stressedValue: Double,
    val holdingImpacts: List<HoldingImpact>
)
