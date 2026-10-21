package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.IpoApiService
import com.fyp.basarattradeinvest.domain.model.ipo.IpoCalendarEvent
import com.fyp.basarattradeinvest.domain.model.ipo.IpoItem
import com.fyp.basarattradeinvest.domain.model.ipo.IpoPerformanceSummary
import com.fyp.basarattradeinvest.domain.model.ipo.toDomain
import com.fyp.basarattradeinvest.domain.repository.IpoRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class IpoRepositoryImpl(
    private val api: IpoApiService = NetworkClient.ipoApiService
) : IpoRepository {

    override suspend fun getIpos(): Result<List<IpoItem>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getIpos()
            if (response.isSuccessful && response.body() != null) {
                val items = response.body()!!.ipos?.map { it.toDomain() } ?: emptyList()
                Result.success(items)
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Unable to load IPOs."))
        }
    }

    override suspend fun getIpoDetail(symbol: String): Result<IpoItem> = withContext(Dispatchers.IO) {
        try {
            val response = api.getIpoDetail(symbol)
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(body.toDomain())
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Unable to load IPO details for $symbol."))
        }
    }

    override suspend fun getIpoCalendar(): Result<List<IpoCalendarEvent>> = withContext(Dispatchers.IO) {
        try {
            val response = api.getIpoCalendar()
            if (response.isSuccessful && response.body() != null) {
                val events = response.body()!!.upcomingMilestones?.map { it.toDomain() } ?: emptyList()
                Result.success(events)
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Unable to load the IPO calendar."))
        }
    }

    override suspend fun getIpoPerformance(): Result<IpoPerformanceSummary> = withContext(Dispatchers.IO) {
        try {
            val response = api.getIpoPerformance()
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(body.toDomain())
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Unable to load IPO performance."))
        }
    }
}
