package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.data.mapper.PortfolioDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.PortfolioApiService
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.CompletedTradeCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.TransactionUpdateDto
import com.fyp.basarattradeinvest.domain.model.portfolio.CompletedTrade
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingDetail
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPerformance
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPnL
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import com.fyp.basarattradeinvest.domain.model.portfolio.TransactionListPage
import com.fyp.basarattradeinvest.domain.repository.PortfolioRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

class PortfolioRepositoryImpl(
    private val apiService: PortfolioApiService = NetworkClient.portfolioApiService
) : PortfolioRepository {

    override suspend fun getPortfolio(): Result<PortfolioOverview> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getPortfolio()
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapPortfolioResponse(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load portfolio overview")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to portfolio service"))
        }
    }

    override suspend fun getHoldings(): Result<List<HoldingItem>> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getHoldings()
            if (response.isSuccessful && response.body() != null) {
                val list = response.body()!!.map { PortfolioDtoMapper.mapHoldingItem(it) }
                Result.success(list)
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load portfolio holdings")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to holdings service"))
        }
    }

    override suspend fun getHoldingDetail(symbol: String): Result<HoldingDetail> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getHoldingDetail(symbol)
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapHoldingDetail(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load holding details for $symbol")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to holding detail service"))
        }
    }

    override suspend fun getPnL(): Result<PortfolioPnL> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getPnL()
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapPnL(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load P&L breakdown")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to P&L service"))
        }
    }

    override suspend fun getAllocation(): Result<PortfolioAllocation> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getAllocation()
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapAllocation(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load portfolio allocation")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to allocation service"))
        }
    }

    override suspend fun getPerformance(period: String): Result<PortfolioPerformance> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getPerformance(period)
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapPerformance(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load performance chart")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to performance service"))
        }
    }

    override suspend fun getTransactions(
        page: Int,
        limit: Int,
        symbol: String?,
        transactionType: String?,
        fromDate: String?,
        toDate: String?
    ): Result<TransactionListPage> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getTransactions(
                page = page,
                limit = limit,
                symbol = symbol,
                transactionType = transactionType,
                fromDate = fromDate,
                toDate = toDate
            )
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapTransactionList(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load transaction history")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to transaction history service"))
        }
    }

    override suspend fun getTransactionById(transactionId: String): Result<PortfolioTransaction> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getTransactionById(transactionId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapTransaction(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Unable to load transaction")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Unable to connect to transaction service"))
        }
    }

    override suspend fun createTransaction(
        symbol: String,
        type: String,
        quantity: Double,
        price: Double,
        fee: Double,
        date: String
    ): Result<PortfolioTransaction> = withContext(Dispatchers.IO) {
        try {
            val req = TransactionCreateDto(
                symbol = symbol.trim().uppercase(),
                transactionType = type.trim().uppercase(),
                quantity = quantity,
                price = price,
                fee = fee,
                transactionDate = date
            )
            val response = apiService.createTransaction(req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapTransaction(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Failed to record transaction")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Network error creating transaction"))
        }
    }

    override suspend fun updateTransaction(
        transactionId: String,
        quantity: Double?,
        price: Double?,
        fee: Double?,
        date: String?
    ): Result<PortfolioTransaction> = withContext(Dispatchers.IO) {
        try {
            val req = TransactionUpdateDto(
                quantity = quantity,
                price = price,
                fee = fee,
                transactionDate = date
            )
            val response = apiService.updateTransaction(transactionId, req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapTransaction(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Failed to update transaction")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Network error updating transaction"))
        }
    }

    override suspend fun deleteTransaction(transactionId: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.deleteTransaction(transactionId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Failed to delete transaction")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Network error deleting transaction"))
        }
    }

    override suspend fun recordCompletedTrade(
        symbol: String,
        quantity: Double,
        buyPrice: Double,
        buyDate: String,
        buyFee: Double,
        sellPrice: Double,
        sellDate: String,
        sellFee: Double
    ): Result<CompletedTrade> = withContext(Dispatchers.IO) {
        try {
            val req = CompletedTradeCreateDto(
                symbol = symbol.trim().uppercase(),
                quantity = quantity,
                buyPrice = buyPrice,
                buyDate = buyDate,
                buyFee = buyFee,
                sellPrice = sellPrice,
                sellDate = sellDate,
                sellFee = sellFee
            )
            val response = apiService.recordCompletedTrade(req)
            if (response.isSuccessful && response.body() != null) {
                Result.success(PortfolioDtoMapper.mapCompletedTrade(response.body()!!))
            } else {
                val errorMsg = parseErrorMessage(response.errorBody()?.string(), response.code(), "Failed to record completed trade")
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(Exception(e.localizedMessage ?: "Network error recording completed trade"))
        }
    }

    private fun parseErrorMessage(errorBody: String?, statusCode: Int, defaultMsg: String): String {
        if (errorBody.isNullOrBlank()) {
            return when (statusCode) {
                401 -> "Session expired. Please log in again."
                403 -> "You do not have permission to perform this action."
                404 -> "Requested portfolio resource not found."
                422 -> "Invalid input data. Please verify your fields."
                else -> defaultMsg
            }
        }
        return try {
            val map = com.google.gson.Gson().fromJson(errorBody, Map::class.java)
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
