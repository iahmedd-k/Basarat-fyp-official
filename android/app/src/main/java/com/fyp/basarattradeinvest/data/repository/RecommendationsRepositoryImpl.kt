package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.data.mapper.RecommendationsDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.RecommendationsApiService
import com.fyp.basarattradeinvest.data.remote.dto.recommendations.EngineWeightsRequestDto
import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationDetail
import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import com.fyp.basarattradeinvest.domain.model.recommendations.TargetStop
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.ConcurrentHashMap
import java.util.Locale

class RecommendationsRepositoryImpl(
    private val apiService: RecommendationsApiService = NetworkClient.recommendationsApiService
) : RecommendationsRepository {

    private data class CachedRecommendationDetail(
        val detail: RecommendationDetail,
        val cachedAt: Long
    )

    companion object {
        private const val RECOMMENDATION_DETAIL_CACHE_TTL_MS = 5 * 60 * 1000L
        private val recommendationDetailCache = ConcurrentHashMap<String, CachedRecommendationDetail>()

        fun getCachedRecommendationDetail(symbol: String): RecommendationDetail? {
            val key = symbol.trim().uppercase(Locale.ROOT)
            val cached = recommendationDetailCache[key] ?: return null
            if (System.currentTimeMillis() - cached.cachedAt > RECOMMENDATION_DETAIL_CACHE_TTL_MS) {
                recommendationDetailCache.remove(key, cached)
                return null
            }
            return cached.detail
        }
    }

    private fun cacheRecommendationDetail(detail: RecommendationDetail): RecommendationDetail {
        recommendationDetailCache[detail.symbol.trim().uppercase(Locale.ROOT)] = CachedRecommendationDetail(
            detail = detail,
            cachedAt = System.currentTimeMillis()
        )
        return detail
    }

    private fun targetLevelText(value: Double?): String =
        value?.let { String.format(Locale.US, "PKR %.2f", it) } ?: "unavailable"

    override suspend fun getRecommendations(
        riskProfile: String?,
        sector: String?,
        limit: Int
    ): Result<List<StockRecommendation>> = withContext(Dispatchers.IO) {
        val normalizedProfile = riskProfile?.trim()?.lowercase() ?: "moderate"
        try {
            val response = apiService.getRecommendations(
                riskProfile = normalizedProfile,
                sector = sector,
                limit = limit
            )
            val rawItems = response.body()?.recommendations
            if (response.isSuccessful && !rawItems.isNullOrEmpty()) {
                val list = rawItems.map {
                    RecommendationsDtoMapper.mapRecommendationItem(it)
                }
                Result.success(list)
            } else {
                Result.failure(Exception("Recommendations are unavailable (${response.code()})"))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getLiveRecommendations(
        riskProfile: String?,
        sector: String?,
        limit: Int
    ): Result<List<StockRecommendation>> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getRecommendations(
                riskProfile = riskProfile?.trim()?.lowercase() ?: "moderate",
                sector = sector,
                limit = limit
            )
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(
                    body.recommendations.mapNotNull { item ->
                        if (item.symbol.isNullOrBlank()) null
                        else RecommendationsDtoMapper.mapRecommendationItem(item)
                    }
                )
            } else {
                Result.failure(Exception("Unable to load live smart selections (${response.code()})"))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(Exception(error.message ?: "Unable to load live smart selections"))
        }
    }

    override suspend fun getRecommendationDetail(symbol: String, knownPrice: Double?): Result<RecommendationDetail> = withContext(Dispatchers.IO) {
        val sym = symbol.trim().uppercase()
        getCachedRecommendationDetail(sym)?.let { return@withContext Result.success(it) }

        // 0. Resolve live market price for the stock
        var livePrice: Double? = knownPrice?.takeIf { it > 0.0 }
        if (livePrice == null) {
            try {
                val overview = NetworkClient.stocksApiService.getStockOverview(sym)
                if (overview.isSuccessful && overview.body() != null) {
                    val p = overview.body()!!.currentPrice ?: overview.body()!!.ltp
                    if (p != null && p > 0.0) {
                        livePrice = p
                    }
                }
            } catch (_: Exception) {}
        }

        // 1. Try real recommendation detail API
        val fresh = try {
            val response = apiService.getRecommendationDetail(sym)
            if (response.isSuccessful && response.body() != null) {
                RecommendationsDtoMapper.mapRecommendationDetail(response.body()!!)
            } else null
        } catch (_: Exception) { null }

        val freshMapped = fresh?.let {
            it.copy(
                currentPrice = livePrice ?: it.currentPrice?.takeIf { p -> p > 0.0 },
                targetPrice = it.targetPrice?.takeIf { p -> p > 0.0 },
                stopLoss = it.stopLoss?.takeIf { p -> p > 0.0 }
            )
        }

        // 2. The per-symbol route recomputes live and withholds its verdict whenever its
        // indicator inputs lag the quote feed (decision.suppressed), while the list route serves
        // the engine's last published batch and still carries the signal with its ATR levels.
        // Take the batch's verdict and levels so this screen agrees with the list, and leave the
        // suppression reason on screen so the reader can see the live recompute declined.
        val needsBatch = freshMapped == null || freshMapped.targetPrice == null || freshMapped.stopLoss == null
        val batch = if (needsBatch) batchRowDetail(sym, livePrice) else null

        val merged = when {
            freshMapped != null && batch != null -> freshMapped.copy(
                signal = batch.signal,
                confidence = batch.confidence,
                compositeScore = batch.compositeScore,
                targetPrice = batch.targetPrice,
                stopLoss = batch.stopLoss,
                currentPrice = batch.currentPrice ?: freshMapped.currentPrice,
                atr14 = freshMapped.atr14 ?: batch.atr14
            )
            freshMapped != null -> freshMapped
            else -> batch
        }

        return@withContext if (merged != null) {
            Result.success(cacheRecommendationDetail(merged))
        } else {
            Result.failure(Exception("No recommendation is available for $sym"))
        }
    }

    /** The symbol's row from the engine's published recommendation batch, or null when absent. */
    private suspend fun batchRowDetail(sym: String, livePrice: Double?): RecommendationDetail? = try {
        val body = apiService.getRecommendations(limit = 100).body()
        val match = body?.recommendations?.firstOrNull {
            it.symbol?.equals(sym, ignoreCase = true) == true
        }
        if (match == null) {
            null
        } else {
            val stockRec = RecommendationsDtoMapper.mapRecommendationItem(match)
            val target = stockRec.targetPrice?.takeIf { it > 0.0 }
            val stop = stockRec.stopLoss?.takeIf { it > 0.0 }
            RecommendationDetail(
                symbol = sym,
                signal = stockRec.signal,
                confidence = stockRec.confidence,
                compositeScore = stockRec.compositeScore,
                individualSignals = emptyMap(),
                targetPrice = target,
                stopLoss = stop,
                expectedRange = null,
                currentPrice = livePrice ?: stockRec.currentPrice?.takeIf { it > 0.0 },
                atr14 = match.risk?.atr14,
                reasoning = mapOf(
                    "ml" to mapOf("direction" to stockRec.summary),
                    "technical" to mapOf(
                        "technical_summary" to "Target ${targetLevelText(target)}, Stop ${targetLevelText(stop)}"
                    )
                ),
                weights = emptyMap()
            )
        }
    } catch (_: Exception) {
        null
    }

    override suspend fun getTargetStop(symbol: String, knownPrice: Double?): Result<TargetStop> = withContext(Dispatchers.IO) {
        val sym = symbol.trim().uppercase()
        var livePrice: Double? = knownPrice?.takeIf { it > 0.0 }
        if (livePrice == null) {
            try {
                val overview = NetworkClient.stocksApiService.getStockOverview(sym)
                if (overview.isSuccessful && overview.body() != null) {
                    val p = overview.body()!!.currentPrice ?: overview.body()!!.ltp
                    if (p != null && p > 0.0) {
                        livePrice = p
                    }
                }
            } catch (_: Exception) {}
        }

        try {
            val response = apiService.getTargetStop(sym)
            if (response.isSuccessful && response.body() != null) {
                val ts = RecommendationsDtoMapper.mapTargetStop(response.body()!!)
                val stockPrice = livePrice ?: ts.currentPrice?.takeIf { it > 0.0 }
                val target = ts.targetPrice?.takeIf { it > 0.0 }
                val stop = ts.stopLoss?.takeIf { it > 0.0 }

                if (target != null && stop != null) {
                    return@withContext Result.success(
                        ts.copy(
                            currentPrice = stockPrice,
                            targetPrice = target,
                            stopLoss = stop
                        )
                    )
                }
                return@withContext Result.failure(
                    Exception("The backend sends no target or stop level for $sym")
                )
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            return@withContext Result.failure(e)
        }
        Result.failure(Exception("The backend sends no target or stop level for $sym"))
    }

    override suspend fun getLiveTargetStop(symbol: String): Result<TargetStop> = withContext(Dispatchers.IO) {
        val normalizedSymbol = symbol.trim().uppercase(Locale.ROOT)
        try {
            val response = apiService.getTargetStop(normalizedSymbol)
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(RecommendationsDtoMapper.mapTargetStop(body))
            } else {
                Result.failure(Exception("Live target and stop levels are unavailable (${response.code()})"))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Result.failure(Exception(error.message ?: "Live target and stop levels are unavailable"))
        }
    }

    override suspend fun getEngineWeights(): Result<EngineWeights> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getEngineWeights()
            if (response.isSuccessful && response.body() != null) {
                Result.success(RecommendationsDtoMapper.mapEngineWeights(response.body()!!))
            } else {
                Result.failure(Exception("Engine weights are unavailable (${response.code()})"))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun setEngineWeights(
        gruWeight: Double,
        technicalWeight: Double,
        fundamentalWeight: Double
    ): Result<EngineWeights> = withContext(Dispatchers.IO) {
        try {
            val request = EngineWeightsRequestDto(
                // Send the new ML field and legacy GRU alias with the same UI weight.
                gruWeight = gruWeight,
                mlWeight = gruWeight,
                technicalWeight = technicalWeight,
                fundamentalWeight = fundamentalWeight,
                sentimentWeight = 0.0
            )
            val response = apiService.setEngineWeights(request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(RecommendationsDtoMapper.mapEngineWeights(response.body()!!))
            } else {
                Result.failure(Exception("Failed to update engine weights (${response.code()})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

}
