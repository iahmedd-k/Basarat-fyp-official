package com.fyp.basarattradeinvest.portfolio

import com.fyp.basarattradeinvest.data.mapper.PortfolioDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.PortfolioApiService
import com.fyp.basarattradeinvest.data.remote.dto.portfolio.*
import com.fyp.basarattradeinvest.data.repository.PortfolioRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.portfolio.*
import com.fyp.basarattradeinvest.domain.repository.PortfolioRepository
import com.fyp.basarattradeinvest.domain.usecase.portfolio.*
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.Response

class PortfolioModuleUnitTest {

    private val gson = Gson()

    @Test
    fun testPortfolioOverviewDto_mapping() {
        val json = """
            {
                "summary": {
                    "total_invested": "1250000.00",
                    "current_value": "1425800.00",
                    "total_pnl": "175800.00",
                    "total_pnl_percent": 14.064,
                    "today_pnl": "12450.00"
                },
                "holdings": [
                    {
                        "symbol": "LUCK",
                        "quantity": "500",
                        "average_cost": "380.00",
                        "company_name": "Lucky Cement Limited",
                        "sector": "Cement",
                        "current_price": "412.50",
                        "market_value": "206250.00",
                        "unrealized_pnl": "16250.00",
                        "unrealized_pnl_percent": 8.55,
                        "portfolio_weight": 14.47,
                        "price_updated_at": "2026-09-23T10:00:00Z",
                        "price_status": "AVAILABLE"
                    }
                ],
                "updated_at": "2026-09-23T10:05:00Z"
            }
        """.trimIndent()

        val dto = gson.fromJson(json, PortfolioResponseDto::class.java)
        assertEquals("1250000.00", dto.summary.totalInvested)
        assertEquals(1, dto.holdings.size)

        val domain = PortfolioDtoMapper.mapPortfolioResponse(dto)
        assertEquals(1250000.00, domain.summary.totalInvested, 0.01)
        assertEquals(1425800.00, domain.summary.currentValue, 0.01)
        assertEquals(175800.00, domain.summary.totalPnl, 0.01)
        assertEquals(14.064, domain.summary.totalPnlPercent, 0.001)
        assertEquals(12450.00, domain.summary.todayPnl, 0.01)

        val holding = domain.holdings[0]
        assertEquals("LUCK", holding.symbol)
        assertEquals(500.0, holding.quantity, 0.01)
        assertEquals(380.00, holding.averageCost, 0.01)
        assertEquals(412.50, holding.currentPrice!!, 0.01)
        assertEquals(16250.00, holding.unrealizedPnl!!, 0.01)
        assertEquals(8.55, holding.unrealizedPnlPercent!!, 0.01)
        assertEquals(14.47, holding.portfolioWeight!!, 0.01)
    }

    @Test
    fun testHoldingDetailDto_mapping() {
        val json = """
            {
                "symbol": "OGDC",
                "company_name": "Oil and Gas Development Co",
                "sector": "Oil and Gas",
                "quantity": "200",
                "average_cost": "135.00",
                "current_price": "145.20",
                "invested_value": "27000.00",
                "market_value": "29040.00",
                "unrealized_pnl": "2040.00",
                "unrealized_pnl_percent": 7.55,
                "realized_pnl": "500.00",
                "portfolio_weight": 2.04,
                "transactions": [
                    {
                        "id": "tx_123",
                        "symbol": "OGDC",
                        "transaction_type": "BUY",
                        "quantity": "200",
                        "price": "135.00",
                        "fee": "15.00",
                        "transaction_date": "2026-09-15",
                        "created_at": "2026-09-15T12:00:00Z",
                        "updated_at": "2026-09-15T12:00:00Z"
                    }
                ],
                "price_updated_at": "2026-09-23T10:00:00Z",
                "price_status": "AVAILABLE"
            }
        """.trimIndent()

        val dto = gson.fromJson(json, HoldingDetailResponseDto::class.java)
        val domain = PortfolioDtoMapper.mapHoldingDetail(dto)
        assertEquals("OGDC", domain.symbol)
        assertEquals(27000.00, domain.investedValue, 0.01)
        assertEquals(29040.00, domain.marketValue!!, 0.01)
        assertEquals(1, domain.transactions.size)
        assertEquals("tx_123", domain.transactions[0].id)
        assertEquals("BUY", domain.transactions[0].transactionType)
    }

    @Test
    fun testPnLDto_mapping() {
        val json = """
            {
                "realized_pnl": "45000.00",
                "unrealized_pnl": "130800.00",
                "total_pnl": "175800.00",
                "total_pnl_percent": 14.06,
                "today_pnl": "12450.00"
            }
        """.trimIndent()

        val dto = gson.fromJson(json, PnLResponseDto::class.java)
        val domain = PortfolioDtoMapper.mapPnL(dto)
        assertEquals(45000.00, domain.realizedPnl, 0.01)
        assertEquals(130800.00, domain.unrealizedPnl, 0.01)
        assertEquals(175800.00, domain.totalPnl, 0.01)
        assertEquals(14.06, domain.totalPnlPercent, 0.01)
        assertEquals(12450.00, domain.todayPnl, 0.01)
    }

    @Test
    fun testAllocationDto_mapping() {
        val json = """
            {
                "by_stock": [
                    { "symbol": "LUCK", "market_value": "500000.00", "percentage": 35.0 },
                    { "symbol": "OGDC", "market_value": "300000.00", "percentage": 21.0 }
                ],
                "by_sector": [
                    { "sector": "Cement", "market_value": "500000.00", "percentage": 35.0 },
                    { "sector": "Oil and Gas", "market_value": "300000.00", "percentage": 21.0 }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, AllocationResponseDto::class.java)
        val domain = PortfolioDtoMapper.mapAllocation(dto)
        assertEquals(2, domain.byStock.size)
        assertEquals("LUCK", domain.byStock[0].symbol)
        assertEquals(35.0, domain.byStock[0].percentage, 0.01)
        assertEquals(2, domain.bySector.size)
        assertEquals("Cement", domain.bySector[0].sector)
    }

    @Test
    fun testCompletedTradeDto_mapping() {
        val json = """
            {
                "symbol": "SYS",
                "quantity": "100",
                "buy_price": "400.00",
                "buy_date": "2026-08-01",
                "buy_fee": "20.00",
                "sell_price": "450.00",
                "sell_date": "2026-09-01",
                "sell_fee": "22.50",
                "holding_period_days": 31,
                "total_invested": "40020.00",
                "total_proceeds": "44977.50",
                "realized_pnl": "4957.50",
                "realized_pnl_percent": 12.387,
                "buy_transaction": {
                    "id": "tx_b1",
                    "symbol": "SYS",
                    "transaction_type": "BUY",
                    "quantity": "100",
                    "price": "400.00",
                    "fee": "20.00",
                    "transaction_date": "2026-08-01",
                    "created_at": "2026-08-01T10:00:00Z",
                    "updated_at": "2026-08-01T10:00:00Z"
                },
                "sell_transaction": {
                    "id": "tx_s1",
                    "symbol": "SYS",
                    "transaction_type": "SELL",
                    "quantity": "100",
                    "price": "450.00",
                    "fee": "22.50",
                    "transaction_date": "2026-09-01",
                    "created_at": "2026-09-01T10:00:00Z",
                    "updated_at": "2026-09-01T10:00:00Z"
                }
            }
        """.trimIndent()

        val dto = gson.fromJson(json, CompletedTradeResponseDto::class.java)
        val domain = PortfolioDtoMapper.mapCompletedTrade(dto)
        assertEquals("SYS", domain.symbol)
        assertEquals(31, domain.holdingPeriodDays)
        assertEquals(4957.50, domain.realizedPnl, 0.01)
        assertEquals(12.387, domain.realizedPnlPercent, 0.001)
        assertEquals("tx_b1", domain.buyTransaction.id)
        assertEquals("tx_s1", domain.sellTransaction.id)
    }

    @Test
    fun testRepository_getPortfolio_success() = runBlocking {
        val fakeApi = object : FakePortfolioApiService() {
            override suspend fun getPortfolio(): Response<PortfolioResponseDto> {
                val dto = PortfolioResponseDto(
                    summary = PortfolioSummaryDto("1000", "1100", "100", 10.0, "10"),
                    holdings = emptyList(),
                    updatedAt = "2026-09-23T10:00:00Z"
                )
                return Response.success(dto)
            }
        }
        val repo = PortfolioRepositoryImpl(fakeApi)
        val result = repo.getPortfolio()
        assertTrue(result.isSuccess)
        assertEquals(1100.0, result.getOrThrow().summary.currentValue, 0.01)
    }

    @Test
    fun testRepository_getPortfolio_unauthorizedError() = runBlocking {
        val fakeApi = object : FakePortfolioApiService() {
            override suspend fun getPortfolio(): Response<PortfolioResponseDto> {
                val errorBody = "{\"success\":false,\"error\":{\"code\":\"UNAUTHORIZED\",\"message\":\"Not authenticated\"}}"
                    .toResponseBody("application/json".toMediaTypeOrNull())
                return Response.error(401, errorBody)
            }
        }
        val repo = PortfolioRepositoryImpl(fakeApi)
        val result = repo.getPortfolio()
        assertTrue(result.isFailure)
        assertEquals("Not authenticated", result.exceptionOrNull()?.message)
    }

    @Test
    fun testRepository_createTransaction_success() = runBlocking {
        val fakeApi = object : FakePortfolioApiService() {
            override suspend fun createTransaction(request: TransactionCreateDto): Response<TransactionResponseDto> {
                val dto = TransactionResponseDto(
                    id = "tx_999",
                    symbol = request.symbol,
                    transactionType = request.transactionType,
                    quantity = request.quantity.toString(),
                    price = request.price.toString(),
                    fee = request.fee.toString(),
                    transactionDate = request.transactionDate,
                    createdAt = "2026-09-23T10:00:00Z",
                    updatedAt = "2026-09-23T10:00:00Z"
                )
                return Response.success(dto)
            }
        }
        val repo = PortfolioRepositoryImpl(fakeApi)
        val result = repo.createTransaction("OGDC", "BUY", 100.0, 145.0, 10.0, "2026-09-23")
        assertTrue(result.isSuccess)
        val tx = result.getOrThrow()
        assertEquals("tx_999", tx.id)
        assertEquals("OGDC", tx.symbol)
        assertEquals("BUY", tx.transactionType)
    }

    @Test
    fun testRepository_deleteTransaction_success() = runBlocking {
        val fakeApi = object : FakePortfolioApiService() {
            override suspend fun deleteTransaction(transactionId: String): Response<Unit> {
                return Response.success(Unit)
            }
        }
        val repo = PortfolioRepositoryImpl(fakeApi)
        val result = repo.deleteTransaction("tx_999")
        assertTrue(result.isSuccess)
    }

    @Test
    fun testUseCases_getHoldingDetail_success() = runBlocking {
        val fakeRepo = object : FakePortfolioRepository() {
            override suspend fun getHoldingDetail(symbol: String): Result<HoldingDetail> {
                return Result.success(
                    HoldingDetail(
                        symbol = symbol,
                        companyName = "Lucky Cement",
                        sector = "Cement",
                        quantity = 500.0,
                        averageCost = 380.0,
                        currentPrice = 412.0,
                        investedValue = 190000.0,
                        marketValue = 206000.0,
                        unrealizedPnl = 16000.0,
                        unrealizedPnlPercent = 8.42,
                        realizedPnl = 0.0,
                        portfolioWeight = 15.0,
                        transactions = emptyList(),
                        priceUpdatedAt = null,
                        priceStatus = "AVAILABLE"
                    )
                )
            }
        }
        val useCase = GetHoldingDetailUseCase(fakeRepo)
        val result = useCase("LUCK")
        assertTrue(result.isSuccess)
        assertEquals("LUCK", result.getOrThrow().symbol)
        assertEquals(500.0, result.getOrThrow().quantity, 0.01)
    }

    private open class FakePortfolioApiService : PortfolioApiService {
        override suspend fun getPortfolio(): Response<PortfolioResponseDto> = throw NotImplementedError()
        override suspend fun getHoldings(): Response<List<HoldingItemDto>> = throw NotImplementedError()
        override suspend fun getHoldingDetail(symbol: String): Response<HoldingDetailResponseDto> = throw NotImplementedError()
        override suspend fun getPnL(): Response<PnLResponseDto> = throw NotImplementedError()
        override suspend fun getAllocation(): Response<AllocationResponseDto> = throw NotImplementedError()
        override suspend fun getPerformance(period: String): Response<PerformanceResponseDto> = throw NotImplementedError()
        override suspend fun getTransactions(page: Int, limit: Int, symbol: String?, transactionType: String?, fromDate: String?, toDate: String?): Response<TransactionListResponseDto> = throw NotImplementedError()
        override suspend fun createTransaction(request: TransactionCreateDto): Response<TransactionResponseDto> = throw NotImplementedError()
        override suspend fun getTransactionById(transactionId: String): Response<TransactionResponseDto> = throw NotImplementedError()
        override suspend fun updateTransaction(transactionId: String, request: TransactionUpdateDto): Response<TransactionResponseDto> = throw NotImplementedError()
        override suspend fun deleteTransaction(transactionId: String): Response<Unit> = throw NotImplementedError()
        override suspend fun recordCompletedTrade(request: CompletedTradeCreateDto): Response<CompletedTradeResponseDto> = throw NotImplementedError()
    }

    private open class FakePortfolioRepository : PortfolioRepository {
        override suspend fun getPortfolio(): Result<PortfolioOverview> = Result.failure(NotImplementedError())
        override suspend fun getHoldings(): Result<List<HoldingItem>> = Result.success(emptyList())
        override suspend fun getHoldingDetail(symbol: String): Result<HoldingDetail> = Result.failure(NotImplementedError())
        override suspend fun getPnL(): Result<PortfolioPnL> = Result.success(PortfolioPnL(0.0, 0.0, 0.0, 0.0, 0.0))
        override suspend fun getAllocation(): Result<PortfolioAllocation> = Result.success(PortfolioAllocation(emptyList(), emptyList()))
        override suspend fun getPerformance(period: String): Result<PortfolioPerformance> = Result.success(PortfolioPerformance(period, emptyList()))
        override suspend fun getTransactions(page: Int, limit: Int, symbol: String?, transactionType: String?, fromDate: String?, toDate: String?): Result<TransactionListPage> = Result.success(TransactionListPage(emptyList(), 0, 1, 20))
        override suspend fun getTransactionById(transactionId: String): Result<PortfolioTransaction> = Result.failure(NotImplementedError())
        override suspend fun createTransaction(symbol: String, type: String, quantity: Double, price: Double, fee: Double, date: String): Result<PortfolioTransaction> = Result.failure(NotImplementedError())
        override suspend fun updateTransaction(transactionId: String, quantity: Double?, price: Double?, fee: Double?, date: String?): Result<PortfolioTransaction> = Result.failure(NotImplementedError())
        override suspend fun deleteTransaction(transactionId: String): Result<Unit> = Result.success(Unit)
        override suspend fun recordCompletedTrade(symbol: String, quantity: Double, buyPrice: Double, buyDate: String, buyFee: Double, sellPrice: Double, sellDate: String, sellFee: Double): Result<CompletedTrade> = Result.failure(NotImplementedError())
    }
}
