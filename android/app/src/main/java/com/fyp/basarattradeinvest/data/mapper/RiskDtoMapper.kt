package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloResultResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.RiskVaRResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.StressTestResponseDto
import com.fyp.basarattradeinvest.domain.model.risk.HoldingImpact
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloJob
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloResult
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloStats
import com.fyp.basarattradeinvest.domain.model.risk.PercentileEntry
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.risk.StressTestResult

object RiskDtoMapper {

    fun mapVaR(dto: RiskVaRResponseDto): PortfolioVaR {
        return PortfolioVaR(
            confidence = dto.confidence ?: 95,
            horizon = dto.horizon ?: "1D",
            varValue = dto.varValue ?: 0.0,
            cvarValue = dto.cvarValue ?: 0.0,
            method = dto.method ?: "historical_simulation",
            numObservations = dto.numObservations ?: 0,
            annualizedVolatility = dto.annualizedVolatility ?: 0.0
        )
    }

    fun mapMonteCarloJob(dto: MonteCarloResponseDto): MonteCarloJob {
        return MonteCarloJob(
            jobId = dto.jobId,
            status = dto.status ?: "pending",
            numSimulations = dto.numSimulations,
            horizonDays = dto.horizonDays,
            message = dto.message
        )
    }

    fun mapMonteCarloResult(dto: MonteCarloResultResponseDto): MonteCarloResult {
        // Build ordered percentiles list
        val order = listOf("p1", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "p99")
        val percentilesMap = dto.percentiles ?: emptyMap()
        val percentilesList = mutableListOf<PercentileEntry>()

        for (k in order) {
            val v = percentilesMap[k]
            if (v != null) {
                percentilesList.add(PercentileEntry(percentile = k.uppercase(), value = v))
            }
        }
        // Add any additional keys not in predefined list
        percentilesMap.forEach { (k, v) ->
            if (!order.contains(k.lowercase())) {
                percentilesList.add(PercentileEntry(percentile = k.uppercase(), value = v))
            }
        }

        val statsMap = dto.stats ?: emptyMap()
        val stats = MonteCarloStats(
            meanReturn = parseDoubleSafe(statsMap["mean_return"]),
            stdReturn = parseDoubleSafe(statsMap["std_return"]),
            probLoss = parseDoubleSafe(statsMap["prob_loss"]),
            maxDrawdown = parseDoubleSafe(statsMap["max_drawdown"]),
            bestCase = parseDoubleSafe(statsMap["best_case"])
        )

        return MonteCarloResult(
            jobId = dto.jobId,
            status = dto.status,
            numSimulations = dto.numSimulations ?: 0,
            horizonDays = dto.horizonDays ?: 0,
            params = dto.params ?: emptyMap(),
            percentiles = percentilesList,
            stats = stats,
            pathsSample = dto.pathsSample ?: emptyList(),
            error = dto.error,
            completedAt = dto.completedAt
        )
    }

    fun mapStressTest(dto: StressTestResponseDto): StressTestResult {
        val holdingImpacts = dto.holdingImpacts?.mapNotNull { item ->
            try {
                val symbol = item["symbol"]?.toString() ?: item["ticker"]?.toString() ?: return@mapNotNull null
                val name = item["name"]?.toString() ?: item["company_name"]?.toString()
                val impactPct = parseDoubleSafe(item["impact"] ?: item["loss_pct"] ?: item["portfolio_impact"])
                val impactVal = parseDoubleSafe(item["impact_value"] ?: item["loss_value"])
                val currVal = parseDoubleSafe(item["current_value"])
                val stressedVal = parseDoubleSafe(item["stressed_value"])
                HoldingImpact(
                    symbol = symbol,
                    name = name,
                    impactPct = impactPct,
                    impactValue = impactVal,
                    currentValue = currVal,
                    stressedValue = stressedVal
                )
            } catch (e: Exception) {
                null
            }
        } ?: emptyList()

        return StressTestResult(
            scenario = dto.scenario,
            name = dto.name,
            description = dto.description,
            portfolioImpact = dto.portfolioImpact,
            portfolioImpactValue = dto.portfolioImpactValue,
            worstCaseLoss = dto.worstCaseLoss,
            volatilityMultiplier = dto.volatilityMultiplier,
            recoveryDays = dto.recoveryDays,
            currentValue = dto.currentValue,
            stressedValue = dto.stressedValue,
            holdingImpacts = holdingImpacts
        )
    }

    private fun parseDoubleSafe(value: Any?): Double? {
        if (value == null) return null
        return when (value) {
            is Number -> value.toDouble()
            is String -> value.toDoubleOrNull()
            else -> null
        }
    }
}
