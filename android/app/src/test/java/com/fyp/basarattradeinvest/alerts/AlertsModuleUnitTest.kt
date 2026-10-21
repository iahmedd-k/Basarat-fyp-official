package com.fyp.basarattradeinvest.alerts

import com.fyp.basarattradeinvest.data.mapper.AlertDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.AlertsApiService
import com.fyp.basarattradeinvest.data.remote.dto.alerts.AlertResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.alerts.AlertRuleResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.alerts.QuickAlertRuleCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.alerts.QuickAlertRuleResponseDto
import com.fyp.basarattradeinvest.data.repository.AlertsRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.alerts.GetAlertsUseCase
import com.fyp.basarattradeinvest.domain.usecase.alerts.MarkAlertReadUseCase
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Response

class AlertsModuleUnitTest {

    private class FakeAlertsApiService : AlertsApiService {
        var shouldFail = false
        var lastQuickRequest: QuickAlertRuleCreateDto? = null
        val storedAlerts = mutableListOf<AlertResponseDto>()

        override suspend fun createQuickAlertRule(
            request: QuickAlertRuleCreateDto
        ): Response<QuickAlertRuleResponseDto> {
            lastQuickRequest = request
            if (shouldFail) {
                return Response.error(
                    422,
                    "{\"detail\":\"Validation error\"}".toResponseBody("application/json".toMediaTypeOrNull())
                )
            }

            val symbol = request.symbol ?: "LUCK"
            return Response.success(
                201,
                QuickAlertRuleResponseDto(
                    symbol = symbol,
                    stockName = "Lucky Cement Limited",
                    stockId = "stock-luck-id",
                    basePrice = 825.0,
                    percentThreshold = 3.0,
                    direction = "both",
                    rules = listOf(
                        AlertRuleResponseDto(
                            id = "rule-1",
                            userId = "user-1",
                            stockId = "stock-luck-id",
                            symbol = symbol,
                            stockName = "Lucky Cement Limited",
                            condition = "price_above",
                            threshold = 849.75,
                            isActive = true,
                            createdAt = "2026-09-30T10:00:00Z"
                        )
                    ),
                    message = "Price alert created for $symbol"
                )
            )
        }

        override suspend fun getAlerts(
            page: Int?,
            limit: Int?,
            unreadOnly: Boolean?
        ): Response<List<AlertResponseDto>> {
            if (shouldFail) {
                return Response.error(
                    500,
                    "{\"detail\":\"Internal server error\"}".toResponseBody("application/json".toMediaTypeOrNull())
                )
            }
            val alerts = if (unreadOnly == true) storedAlerts.filterNot { it.isRead } else storedAlerts
            return Response.success(alerts)
        }

        override suspend fun markAlertAsRead(alertId: String): Response<Unit> {
            if (shouldFail) {
                return Response.error(
                    404,
                    "{\"detail\":\"Alert not found\"}".toResponseBody("application/json".toMediaTypeOrNull())
                )
            }
            val index = storedAlerts.indexOfFirst { it.id == alertId }
            if (index >= 0) storedAlerts[index] = storedAlerts[index].copy(isRead = true)
            return Response.success(204, Unit)
        }
    }

    private lateinit var fakeApiService: FakeAlertsApiService
    private lateinit var repository: AlertsRepositoryImpl
    private lateinit var getAlertsUseCase: GetAlertsUseCase
    private lateinit var markReadUseCase: MarkAlertReadUseCase

    @Before
    fun setUp() {
        fakeApiService = FakeAlertsApiService()
        repository = AlertsRepositoryImpl(fakeApiService)
        getAlertsUseCase = GetAlertsUseCase(repository)
        markReadUseCase = MarkAlertReadUseCase(repository)
    }

    @Test
    fun quickRuleUsesSymbolAndBackendDefaults() = runBlocking {
        val result = repository.createQuickAlertRule("luck")

        assertTrue(result.isSuccess)
        assertEquals("LUCK", fakeApiService.lastQuickRequest?.symbol)
        assertNull(fakeApiService.lastQuickRequest?.stockName)
        assertNull(fakeApiService.lastQuickRequest?.stockId)
        assertNull(fakeApiService.lastQuickRequest?.percentThreshold)
        assertNull(fakeApiService.lastQuickRequest?.direction)
        assertEquals("Price alert created for LUCK", result.getOrThrow().message)
        assertEquals(825.0, result.getOrThrow().basePrice, 0.001)
        assertEquals(3.0, result.getOrThrow().percentThreshold, 0.001)
        assertEquals("both", result.getOrThrow().direction)
    }

    @Test
    fun quickRuleReturnsBackendValidationFailure() = runBlocking {
        fakeApiService.shouldFail = true

        val result = repository.createQuickAlertRule("OGDC")

        assertTrue(result.isFailure)
        assertNotNull(result.exceptionOrNull())
    }

    @Test
    fun alertDtoMapperMapsTriggeredAlert() {
        val domain = AlertDtoMapper.mapAlertDtoToDomain(
            AlertResponseDto(
                id = "alert-101",
                userId = "user-1",
                ruleId = "rule-1",
                title = "Price alert",
                message = "LUCK crossed its alert level",
                isRead = false,
                createdAt = "2026-09-30T10:00:00Z"
            )
        )

        assertEquals("alert-101", domain.id)
        assertEquals("Price alert", domain.title)
        assertFalse(domain.isRead)
        assertNotNull(domain.formattedTime)
    }

    @Test
    fun alertHistoryCanBeLoadedAndMarkedRead() = runBlocking {
        fakeApiService.storedAlerts += AlertResponseDto(
            id = "alert-101",
            userId = "user-1",
            ruleId = "rule-1",
            title = "Price alert",
            message = "OGDC crossed its alert level",
            isRead = false,
            createdAt = "2026-09-30T10:00:00Z"
        )

        val alerts = getAlertsUseCase().getOrThrow()
        assertEquals(1, alerts.size)
        assertFalse(alerts.single().isRead)

        assertTrue(markReadUseCase("alert-101").isSuccess)
        assertTrue(getAlertsUseCase().getOrThrow().single().isRead)
    }
}
