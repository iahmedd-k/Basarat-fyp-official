package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.forecast.*
import com.fyp.basarattradeinvest.domain.model.stock.StockForecast
import com.fyp.basarattradeinvest.domain.model.stock.ForecastProbabilities
import com.fyp.basarattradeinvest.domain.model.stock.ForecastModelDetail
import com.fyp.basarattradeinvest.domain.model.stock.ForecastMarketContext
import com.fyp.basarattradeinvest.domain.model.stock.ForecastDirection
import com.fyp.basarattradeinvest.domain.model.stock.ForecastHistory
import com.fyp.basarattradeinvest.domain.model.stock.ForecastActualOutcome
import com.fyp.basarattradeinvest.domain.model.stock.ForecastHistoryRecord

/**
 * Mapper between raw Swagger Forecast DTOs and Clean Domain models
 */
object ForecastDtoMapper {

    fun mapToDomain(dto: ForecastResponseDto, fallbackPrice: Double? = null): StockForecast {
        val probabilitiesDomain = dto.probabilities?.let { p ->
            ForecastProbabilities(
                bullish = p.bullish,
                bearish = p.bearish,
                sideways = p.sideways
            )
        }

        val modelsDomain = dto.models?.mapValues { (_, modelDetail) ->
            ForecastModelDetail(
                direction = modelDetail.direction ?: "unknown",
                bullishPct = modelDetail.bullishPct,
                bearishPct = modelDetail.bearishPct,
                sidewaysPct = modelDetail.sidewaysPct,
                gapPp = modelDetail.gapPp
            )
        } ?: emptyMap()

        val contextDomain = dto.marketContext?.let { mc ->
            ForecastMarketContext(
                marketReturn5d = mc.marketReturn5d,
                marketReturn20d = mc.marketReturn20d,
                stockReturn20d = mc.stockReturn20d,
                stockRelativeReturn20d = mc.stockRelativeReturn20d
            )
        }

        val directionEnum = ForecastDirection.fromString(dto.direction.orEmpty())
        val resolvedPrice = dto.currentPrice?.takeIf { it > 0.0 } ?: fallbackPrice?.takeIf { it > 0.0 }
        val resolvedHorizon = dto.horizon ?: "1W"

        val targetParams = resolveTargets(
            currentPrice = resolvedPrice,
            apiTarget = dto.targetPrice,
            apiStop = dto.stopLoss,
            apiUpside = dto.upsidePct,
            apiDownside = dto.downsidePct,
            apiRr = dto.riskRewardRatio
        )

        return StockForecast(
            symbol = dto.symbol.orEmpty(),
            horizon = resolvedHorizon,
            direction = directionEnum,
            confidence = dto.confidence,
            currentPrice = resolvedPrice,
            targetPrice = targetParams.targetPrice,
            targetDate = dto.targetDate.orEmpty(),
            asOfDate = dto.asOfDate.orEmpty(),
            stopLoss = targetParams.stopLoss,
            upsidePct = targetParams.upsidePct,
            downsidePct = targetParams.downsidePct,
            riskRewardRatio = targetParams.riskRewardRatio,
            signalRating = dto.signalRating,
            modelVersion = dto.modelVersion,
            gateReason = dto.gateReason,
            probabilities = probabilitiesDomain,
            models = modelsDomain,
            marketContext = contextDomain
        )
    }

    /**
     * Re-anchors target price, stop loss, and risk/reward parameters when live stock price
     * becomes available from the market quote or parent screen analysis.
     */
    fun recalculateTargets(forecast: StockForecast, livePrice: Double?): StockForecast {
        val resolvedPrice = forecast.currentPrice?.takeIf { it > 0.0 } ?: livePrice?.takeIf { it > 0.0 }
        val targetParams = resolveTargets(
            currentPrice = resolvedPrice,
            apiTarget = forecast.targetPrice,
            apiStop = forecast.stopLoss,
            apiUpside = forecast.upsidePct,
            apiDownside = forecast.downsidePct,
            apiRr = forecast.riskRewardRatio
        )
        return forecast.copy(
            currentPrice = resolvedPrice,
            targetPrice = targetParams.targetPrice,
            stopLoss = targetParams.stopLoss,
            upsidePct = targetParams.upsidePct,
            downsidePct = targetParams.downsidePct,
            riskRewardRatio = targetParams.riskRewardRatio
        )
    }

    data class TargetParameters(
        val targetPrice: Double?,
        val stopLoss: Double?,
        val upsidePct: Double?,
        val downsidePct: Double?,
        val riskRewardRatio: Double?
    )

    private fun resolveTargets(
        currentPrice: Double?,
        apiTarget: Double?,
        apiStop: Double?,
        apiUpside: Double?,
        apiDownside: Double?,
        apiRr: Double?
    ): TargetParameters {
        val validPrice = currentPrice?.takeIf { it > 0.0 }
        val target = apiTarget?.takeIf { it > 0.0 }
            ?: apiUpside?.let { pct -> validPrice?.let { roundPrice(it * (1.0 + pct / 100.0)) } }
        val stop = apiStop?.takeIf { it > 0.0 }
            ?: apiDownside?.let { pct -> validPrice?.let { roundPrice(it * (1.0 + pct / 100.0)) } }
        val upPct = apiUpside ?: if (target != null && validPrice != null) {
            roundPercent((target - validPrice) / validPrice * 100.0)
        } else null
        val downPct = apiDownside ?: if (stop != null && validPrice != null) {
            roundPercent((stop - validPrice) / validPrice * 100.0)
        } else null
        val rr = apiRr ?: if (upPct != null && downPct != null && downPct != 0.0) {
            roundPercent(kotlin.math.abs(upPct / downPct))
        } else null

        return TargetParameters(
            targetPrice = target,
            stopLoss = stop,
            upsidePct = upPct,
            downsidePct = downPct,
            riskRewardRatio = rr
        )
    }

    private fun roundPrice(value: Double): Double = Math.round(value * 100.0) / 100.0

    private fun roundPercent(value: Double): Double = Math.round(value * 100.0) / 100.0

    fun mapToDomain(dto: ForecastHistoryResponseDto): ForecastHistory {
        val records = dto.history.orEmpty().map { item ->
            val actualDomain = item.actual?.let { act ->
                ForecastActualOutcome(
                    direction = act.direction ?: "unknown",
                    wasCorrect = act.wasCorrect
                )
            }

            ForecastHistoryRecord(
                predictedAt = item.predictedAt.orEmpty(),
                predictedDirection = ForecastDirection.fromString(item.predictedDirection.orEmpty()),
                probabilities = item.probabilities ?: emptyMap(),
                confidence = item.confidence,
                targetDate = item.targetDate.orEmpty(),
                actualOutcome = actualDomain
            )
        }

        return ForecastHistory(
            symbol = dto.symbol.orEmpty(),
            horizon = dto.horizon ?: "1D",
            count = dto.count,
            accuracy = dto.accuracy,
            history = records
        )
    }
}
