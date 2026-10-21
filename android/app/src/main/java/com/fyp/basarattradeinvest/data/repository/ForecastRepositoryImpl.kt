package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.data.mapper.ForecastDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.ForecastApiService
import com.fyp.basarattradeinvest.domain.model.stock.ForecastHistory
import com.fyp.basarattradeinvest.domain.model.stock.StockForecast
import com.fyp.basarattradeinvest.domain.repository.ForecastRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Concrete implementation of ForecastRepository using Retrofit ForecastApiService
 */
class ForecastRepositoryImpl(
    private val apiService: ForecastApiService = NetworkClient.forecastApiService
) : ForecastRepository {

    override suspend fun getStockForecast(
        symbol: String,
        horizon: String
    ): Result<StockForecast> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getStockForecast(symbol = symbol, horizon = horizon)
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    Result.success(ForecastDtoMapper.mapToDomain(body))
                } else {
                    Result.failure(Exception("Forecast response body is empty for $symbol"))
                }
            } else {
                val errorMsg = when (response.code()) {
                    401 -> "Session expired or unauthorized. Please log in."
                    404 -> "Forecast not available for symbol $symbol."
                    503 -> "ML model service temporarily unavailable for $symbol."
                    else -> "Unable to load forecast for $symbol (HTTP ${response.code()})"
                }
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Network error loading forecast for $symbol"))
        }
    }

    override suspend fun getForecastHistory(
        symbol: String,
        horizon: String,
        limit: Int
    ): Result<ForecastHistory> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getForecastHistory(symbol = symbol, horizon = horizon, limit = limit)
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    Result.success(ForecastDtoMapper.mapToDomain(body))
                } else {
                    Result.failure(Exception("Forecast history response body is empty for $symbol"))
                }
            } else {
                val errorMsg = when (response.code()) {
                    401 -> "Session expired or unauthorized. Please log in."
                    404 -> "Forecast history not found for symbol $symbol."
                    else -> "Unable to load forecast history for $symbol (HTTP ${response.code()})"
                }
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Network error loading forecast history for $symbol"))
        }
    }
}
