package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.EtfApiService
import com.fyp.basarattradeinvest.domain.model.etf.EtfHistoryEntry
import com.fyp.basarattradeinvest.domain.model.etf.EtfItem
import com.fyp.basarattradeinvest.domain.model.etf.EtfPerformance
import com.fyp.basarattradeinvest.domain.model.etf.EtfsResult
import com.fyp.basarattradeinvest.domain.model.etf.toDomain
import com.fyp.basarattradeinvest.domain.repository.EtfRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class EtfRepositoryImpl(
    private val api: EtfApiService = NetworkClient.etfApiService
) : EtfRepository {

    override suspend fun getEtfs(): Result<EtfsResult> = withContext(Dispatchers.IO) {
        try {
            val response = api.getEtfs()
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(
                    EtfsResult(
                        total = body.total ?: 0,
                        shariahCount = body.shariahCount ?: 0,
                        conventionalCount = body.conventionalCount ?: 0,
                        etfs = body.etfs?.map { it.toDomain() } ?: emptyList()
                    )
                )
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Unable to load ETFs."))
        }
    }

    override suspend fun getEtfDetail(symbol: String): Result<EtfItem> = withContext(Dispatchers.IO) {
        try {
            val response = api.getEtfDetail(symbol)
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(body.toDomain())
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Unable to load ETF details for $symbol."))
        }
    }

    override suspend fun getEtfHistory(symbol: String, timeframe: String): Result<List<EtfHistoryEntry>> =
        withContext(Dispatchers.IO) {
            try {
                val response = api.getEtfHistory(symbol, timeframe)
                if (response.isSuccessful && response.body() != null) {
                    val entries = response.body()!!.history?.map { it.toDomain() } ?: emptyList()
                    Result.success(entries)
                } else {
                    Result.failure(Exception(NetworkErrorParser.parseError(response)))
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Result.failure(Exception(e.message ?: "Unable to load price history for $symbol."))
            }
        }

    override suspend fun getEtfPerformance(symbol: String): Result<EtfPerformance> = withContext(Dispatchers.IO) {
        try {
            val response = api.getEtfPerformance(symbol)
            val body = response.body()
            if (response.isSuccessful && body != null) {
                Result.success(body.toDomain())
            } else {
                Result.failure(Exception(NetworkErrorParser.parseError(response)))
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(Exception(e.message ?: "Unable to load performance for $symbol."))
        }
    }
}
