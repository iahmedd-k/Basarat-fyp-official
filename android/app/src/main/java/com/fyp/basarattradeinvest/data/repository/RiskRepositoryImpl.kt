package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.data.mapper.RiskDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.RiskApiService
import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloRequestDto
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloJob
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloResult
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.risk.StressTestResult
import com.fyp.basarattradeinvest.domain.repository.RiskRepository
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class RiskRepositoryImpl(
    private val apiService: RiskApiService = NetworkClient.riskApiService
) : RiskRepository {

    override suspend fun getValueAtRisk(confidence: Int?, horizon: String?): Result<PortfolioVaR> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getValueAtRisk(confidence = confidence, horizon = horizon)
            if (response.isSuccessful && response.body() != null) {
                Result.success(RiskDtoMapper.mapVaR(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to calculate Value at Risk")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to risk service"))
        }
    }

    override suspend fun startMonteCarloSimulation(numSimulations: Int, horizonDays: Int): Result<MonteCarloJob> = withContext(Dispatchers.IO) {
        try {
            val request = MonteCarloRequestDto(numSimulations = numSimulations, horizonDays = horizonDays)
            val response = apiService.startMonteCarloSimulation(request)
            if ((response.isSuccessful || response.code() == 202) && response.body() != null) {
                Result.success(RiskDtoMapper.mapMonteCarloJob(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to start Monte Carlo simulation")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to initiate Monte Carlo simulation"))
        }
    }

    override suspend fun getMonteCarloResult(taskId: String): Result<MonteCarloResult> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getMonteCarloResult(taskId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(RiskDtoMapper.mapMonteCarloResult(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to retrieve simulation results")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Network error checking simulation status"))
        }
    }

    override suspend fun getStressTest(scenario: String?): Result<StressTestResult> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getStressTest(scenario)
            if (response.isSuccessful && response.body() != null) {
                Result.success(RiskDtoMapper.mapStressTest(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to run stress test scenario")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to stress test service"))
        }
    }

    private fun parseErrorMessage(errorBody: String?, statusCode: Int, defaultMsg: String): String {
        if (errorBody.isNullOrBlank()) {
            return when (statusCode) {
                401 -> "Session expired. Please log in again."
                403 -> "You do not have permission to view risk analytics."
                404 -> "Requested risk analytics resource not found."
                422 -> "Invalid risk parameters. Please verify inputs."
                else -> defaultMsg
            }
        }
        return try {
            val map = Gson().fromJson(errorBody, Map::class.java)
            val detail = map["detail"] as? String
            val msg = map["message"] as? String
            val errObj = map["error"]
            when {
                !detail.isNullOrBlank() -> detail
                !msg.isNullOrBlank() -> msg
                errObj is Map<*, *> && errObj["message"] != null -> errObj["message"].toString()
                errObj is String -> errObj
                else -> defaultMsg
            }
        } catch (e: Exception) {
            defaultMsg
        }
    }
}
