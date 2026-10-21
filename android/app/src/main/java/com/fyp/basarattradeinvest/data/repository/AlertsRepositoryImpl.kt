package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.mapper.AlertDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.AlertsApiService
import com.fyp.basarattradeinvest.data.remote.dto.alerts.QuickAlertRuleCreateDto
import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem
import com.fyp.basarattradeinvest.domain.model.alerts.QuickAlertResult
import com.fyp.basarattradeinvest.domain.repository.AlertsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class AlertsRepositoryImpl(
    private val apiService: AlertsApiService = NetworkClient.alertsApiService
) : AlertsRepository {

    override suspend fun createQuickAlertRule(symbol: String): Result<QuickAlertResult> = withContext(Dispatchers.IO) {
        try {
            val request = QuickAlertRuleCreateDto(
                symbol = symbol.trim().uppercase().takeIf { it.isNotBlank() }
                    ?: return@withContext Result.failure(IllegalArgumentException("A stock symbol is required"))
            )
            val response = apiService.createQuickAlertRule(request)
            if (response.isSuccessful && response.body() != null) {
                val dto = response.body()!!
                Result.success(
                    QuickAlertResult(
                        symbol = dto.symbol,
                        stockId = dto.stockId,
                        basePrice = dto.basePrice,
                        percentThreshold = dto.percentThreshold,
                        direction = dto.direction,
                        message = dto.message
                    )
                )
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getAlerts(
        page: Int?,
        limit: Int?,
        unreadOnly: Boolean?
    ): Result<List<AlertItem>> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getAlerts(
                page = page,
                limit = limit,
                unreadOnly = unreadOnly
            )
            if (response.isSuccessful) {
                val dtoList = response.body() ?: emptyList()
                val domainList = dtoList.map { AlertDtoMapper.mapAlertDtoToDomain(it) }
                Result.success(domainList)
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun markAlertAsRead(alertId: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.markAlertAsRead(alertId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
