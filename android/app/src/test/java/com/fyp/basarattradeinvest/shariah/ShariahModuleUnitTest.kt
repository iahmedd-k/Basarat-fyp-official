package com.fyp.basarattradeinvest.shariah

import com.fyp.basarattradeinvest.data.mapper.ShariahDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.ShariahApiService
import com.fyp.basarattradeinvest.data.remote.dto.live.RestQuotesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.live.WsQuoteDataDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahCriteriaResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahKmi30ResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahPurificationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahScreeningResponseDto
import com.fyp.basarattradeinvest.data.repository.ShariahRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.shariah.CalculateDividendPurificationUseCase
import com.fyp.basarattradeinvest.domain.usecase.shariah.GetKmi30ConstituentsUseCase
import com.fyp.basarattradeinvest.domain.usecase.shariah.GetStockShariahCriteriaUseCase
import com.fyp.basarattradeinvest.domain.usecase.shariah.GetStockShariahScreeningUseCase
import com.google.gson.Gson
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

/**
 * Fixtures below are verbatim bodies captured from GET /api/v1/shariah/... so a field renamed or
 * dropped by the backend fails here instead of rendering as a blank column in the app.
 */
class ShariahModuleUnitTest {

    private companion object {
        const val KMI30_JSON = """
        {
          "index": "KMI-30",
          "total_constituents": 30,
          "as_of": "2025-12-31T00:00:00Z",
          "is_stale": true,
          "effective_from": "2026-05-25T00:00:00Z",
          "source_url": "https://dps.psx.com.pk/download/attachment/277332-1.pdf",
          "constituents": [
            {"symbol":"AIRLINK","name":"Air Link Communication Limited","is_shariah_compliant":true,
             "debt_ratio":0.3266,"interest_income_ratio":0.0038,
             "data_as_of":"2025-12-31T00:00:00+00:00","purification_rate_provisional":true},
            {"symbol":"MEBL","name":"Meezan Bank Limited","is_shariah_compliant":true,
             "debt_ratio":null,"interest_income_ratio":null,
             "data_as_of":"2025-12-31T00:00:00+00:00","purification_rate_provisional":false},
            {"symbol":"SYS","name":"Systems Limited","is_shariah_compliant":true,
             "debt_ratio":0.085,"interest_income_ratio":0.0009,
             "data_as_of":"2025-12-31T00:00:00+00:00","purification_rate_provisional":false}
          ]
        }
        """

        const val SCREENING_JSON = """
        {
          "symbol": "AIRLINK",
          "screening_available": true,
          "is_shariah_compliant": true,
          "overall_score": 100.0,
          "screening_method": "PSX KMI-30 screening notice PSX/N-610 (2026-05-15)",
          "screened_at": "2025-12-31T00:00:00",
          "data_as_of": "2025-12-31T00:00:00Z",
          "data_is_stale": true,
          "effective_from": "2026-05-25T00:00:00Z",
          "source_url": "https://dps.psx.com.pk/download/attachment/277332-1.pdf",
          "source_exception": "None (Standard PSX KMI-30 screening)",
          "purification_rate_provisional": true,
          "sector": "TECHNOLOGY & COMMUNICATION",
          "purification_rate": 0.0038,
          "compliance_summary": "AIRLINK is classified by the PSX KMI-30 screening effective 2026-05-25; financial ratios are as of 2025-12-31."
        }
        """

        const val UNSCREENED_JSON = """
        {
          "symbol": "NOTAREALSYM",
          "screening_available": false,
          "is_shariah_compliant": false,
          "overall_score": 0.0,
          "screening_method": "PSX KMI-30 / Meezan Screening Standard",
          "screened_at": "2026-10-04T11:56:17.302593",
          "data_as_of": null,
          "data_is_stale": false,
          "effective_from": null,
          "source_url": "https://www.psx.com.pk",
          "source_exception": "None (Standard PSX KMI-30 screening)",
          "purification_rate_provisional": false,
          "criteria": [],
          "sector": "Commercial & Industrial",
          "purification_rate": 0.0,
          "compliance_summary": "No Shariah screening data is available for NOTAREALSYM; compliance is unverified."
        }
        """

        const val CRITERIA_JSON = """
        {
          "symbol": "AIRLINK",
          "screening_available": true,
          "is_shariah_compliant": true,
          "criteria": [
            {"name":"Core Business Permissibility","threshold":1.0,"value":1.0,"passed":true,
             "description":"Core business activities must be halal and free from prohibited elements.",
             "exception":"None (Fully compliant with PSX standard)"},
            {"name":"Debt to Total Assets Ratio","threshold":37.0,"value":32.66,"passed":true,
             "description":"Total interest-bearing debt / Total Assets must be less than 37%.",
             "exception":"None (Fully compliant with PSX standard)"},
            {"name":"Non-Permissible / Interest Income Ratio","threshold":5.0,"value":0.38,"passed":true,
             "description":"Interest and non-permissible income / Gross Revenue must be under 5%.",
             "exception":"PSX marks the financial-institution row with N/A for debt, investment and income ratios."}
          ],
          "data_as_of": "2025-12-31T00:00:00Z",
          "data_is_stale": true,
          "source_url": "https://dps.psx.com.pk/download/attachment/277332-1.pdf"
        }
        """

        const val PURIFICATION_JSON = """
        {
          "symbol": "AIRLINK",
          "dividend_income": 1000.0,
          "purification_amount": 3.8,
          "purification_rate": 0.0038,
          "notes": "Using the PSX screening rate dated 2025-12-31, calculate PKR 3.80 (0.38% of dividend income). PSX marks this rate provisional and subject to adjustment.",
          "data_as_of": "2025-12-31T00:00:00Z",
          "data_is_stale": true,
          "source_url": "https://dps.psx.com.pk/download/attachment/277332-1.pdf",
          "rate_is_provisional": true
        }
        """

        fun <T> errorResponse(code: Int, body: String): Response<T> =
            Response.error(code, body.toResponseBody("application/json".toMediaTypeOrNull()))
    }

    private val gson = Gson()

    private class FakeShariahApiService : ShariahApiService {
        var shouldFail: Boolean = false
        var lastDividendIncome: Double? = null

        override suspend fun getKmi30Constituents(): Response<ShariahKmi30ResponseDto> {
            if (shouldFail) return errorResponse(500, """{"detail":"Internal Error"}""")
            return Response.success(
                Gson().fromJson(KMI30_JSON, ShariahKmi30ResponseDto::class.java)
            )
        }

        override suspend fun getAllStocks(
            limit: Int,
            offset: Int,
            sortBy: String,
            order: String
        ): Response<RestQuotesResponseDto> {
            if (shouldFail) return errorResponse(500, """{"detail":"Internal Error"}""")
            return Response.success(
                RestQuotesResponseDto(
                    stocks = listOf(
                        WsQuoteDataDto(symbol = "SYSTEMS", current = 412.5, ldcp = 410.0, open = null, high = null, low = null, change = 2.5, changePct = 0.61, volume = 1200, asOf = null, name = "Systems Limited", sector = "TECHNOLOGY & COMMUNICATION", marketCapM = null),
                        WsQuoteDataDto(symbol = "HBL", current = null, ldcp = null, open = null, high = null, low = null, change = null, changePct = null, volume = null, asOf = null, name = null, sector = null, marketCapM = null)
                    ),
                    total = 2,
                    asOf = "2026-10-07T10:53:51+00:00",
                    isStale = true,
                    recommendedPollSeconds = 15
                )
            )
        }

        override suspend fun getShariahScreening(symbol: String): Response<ShariahScreeningResponseDto> {
            if (shouldFail) return errorResponse(500, """{"detail":"Server error"}""")
            val json = if (symbol == "NOTAREALSYM") UNSCREENED_JSON else SCREENING_JSON
            return Response.success(
                Gson().fromJson(json, ShariahScreeningResponseDto::class.java)
            )
        }

        override suspend fun getShariahCriteria(symbol: String): Response<ShariahCriteriaResponseDto> {
            if (shouldFail) return errorResponse(500, """{"detail":"Server error"}""")
            return Response.success(
                Gson().fromJson(CRITERIA_JSON, ShariahCriteriaResponseDto::class.java)
            )
        }

        override suspend fun getShariahPurification(
            symbol: String,
            dividendIncome: Double
        ): Response<ShariahPurificationResponseDto> {
            if (shouldFail) return errorResponse(422, """{"detail":"dividend_income: missing"}""")
            lastDividendIncome = dividendIncome
            return Response.success(
                Gson().fromJson(PURIFICATION_JSON, ShariahPurificationResponseDto::class.java)
            )
        }
    }

    private lateinit var fakeApi: FakeShariahApiService
    private lateinit var repository: ShariahRepositoryImpl

    @Before
    fun setUp() {
        fakeApi = FakeShariahApiService()
        repository = ShariahRepositoryImpl(fakeApi)
    }

    @Test
    fun kmi30Constituent_mapsTheFieldsTheBackendActuallySends() {
        val summary = ShariahDtoMapper.mapKmi30Response(
            gson.fromJson(KMI30_JSON, ShariahKmi30ResponseDto::class.java)
        )

        assertEquals("KMI-30", summary.index)
        assertEquals(30, summary.totalConstituents)
        assertEquals("2025-12-31T00:00:00Z", summary.asOf)
        assertTrue(summary.isStale)
        assertEquals(3, summary.constituents.size)

        val airlink = summary.constituents.first { it.symbol == "AIRLINK" }
        assertEquals("Air Link Communication Limited", airlink.name)
        assertTrue(airlink.isCompliant == true)
        assertEquals(0.0038, airlink.interestIncomeRatio!!, 0.000001)
        assertTrue(airlink.purificationRateProvisional)

        // PSX publishes N/A for a financial institution's ratios; that must stay "no value",
        // never 0.0 — a zero rate would tell the user there is nothing to purify.
        val meezan = summary.constituents.first { it.symbol == "MEBL" }
        assertNull(meezan.interestIncomeRatio)
        assertNull(meezan.debtRatio)
        assertFalse(meezan.purificationRateProvisional)
    }

    @Test
    fun listRowCarriesScreeningDataAndLeavesPriceToTheQuoteLayer() {
        val summary = ShariahDtoMapper.mapKmi30Response(
            gson.fromJson(KMI30_JSON, ShariahKmi30ResponseDto::class.java)
        )
        val row = ShariahDtoMapper.mapConstituentToLegacyStock(summary.constituents.first())

        assertEquals("AIRLINK", row.symbol)
        assertEquals("Air Link Communication Limited", row.companyName)
        assertEquals(0.0038, row.purificationRate!!, 0.000001)
        assertTrue(row.purificationProvisional)
        assertNull(row.price)
        assertNull(row.changePercent)
    }

    @Test
    fun screeningResponse_mapsRealValuesWithoutInventingDefaults() {
        val compliance = ShariahDtoMapper.mapScreeningResponse(
            gson.fromJson(SCREENING_JSON, ShariahScreeningResponseDto::class.java)
        )

        assertTrue(compliance.screeningAvailable)
        assertTrue(compliance.isCompliant)
        assertEquals(100.0, compliance.overallScore!!, 0.001)
        assertEquals("PSX KMI-30 screening notice PSX/N-610 (2026-05-15)", compliance.screeningMethod)
        assertEquals("TECHNOLOGY & COMMUNICATION", compliance.sector)
        assertEquals(0.0038, compliance.purificationRate!!, 0.000001)
        assertTrue(compliance.dataIsStale)
        assertEquals("2025-12-31T00:00:00Z", compliance.dataAsOf)
        assertTrue(compliance.complianceSummary!!.contains("PSX KMI-30 screening"))
    }

    @Test
    fun unscreenedSymbol_isReportedAsNotAvailableAndExplicitNullsStayNull() {
        val compliance = ShariahDtoMapper.mapScreeningResponse(
            gson.fromJson(UNSCREENED_JSON, ShariahScreeningResponseDto::class.java)
        )

        assertFalse(compliance.screeningAvailable)
        assertFalse(compliance.isCompliant)
        assertEquals(0.0, compliance.overallScore!!, 0.001)
        // The backend sends these as explicit nulls for an unscreened symbol; the app must not
        // replace them with a made-up date or sector.
        assertNull(compliance.dataAsOf)
        assertFalse(compliance.dataIsStale)
        assertEquals("No Shariah screening data is available for NOTAREALSYM; compliance is unverified.",
            compliance.complianceSummary)
    }

    @Test
    fun criteriaResponse_mapsThresholdValueAndPsxException() {
        val criteria = ShariahDtoMapper.mapCriteriaResponse(
            gson.fromJson(CRITERIA_JSON, ShariahCriteriaResponseDto::class.java)
        )

        assertEquals(3, criteria.criteria.size)
        assertTrue(criteria.screeningAvailable)

        val debt = criteria.criteria.first { it.name == "Debt to Total Assets Ratio" }
        assertEquals(37.0, debt.threshold!!, 0.001)
        assertEquals(32.66, debt.value!!, 0.001)
        assertTrue(debt.passed == true)
        assertEquals("None (Fully compliant with PSX standard)", debt.exception)

        val income = criteria.criteria.first { it.name.contains("Interest Income") }
        assertTrue(income.exception!!.contains("financial-institution"))
    }

    @Test
    fun purificationResponse_mapsDividendIncome() {
        val result = ShariahDtoMapper.mapPurificationResponse(
            gson.fromJson(PURIFICATION_JSON, ShariahPurificationResponseDto::class.java)
        )

        assertEquals(1000.0, result.dividendIncome, 0.001)
        assertEquals(3.8, result.purificationAmount, 0.0001)
        assertEquals(0.0038, result.purificationRate, 0.000001)
        assertTrue(result.rateIsProvisional)
        assertNotNull(result.notes)
    }

    @Test
    fun repository_returnsRealFailure_whenKmi30CallFails() = runBlocking {
        fakeApi.shouldFail = true

        val summary = repository.getKmi30Constituents()
        assertTrue(summary.isFailure)
        // The 500 must reach the caller as a failure; its text is sanitised centrally, so the
        // server's own body never appears in the UI.
        val summaryMessage = summary.exceptionOrNull()?.message.orEmpty()
        assertFalse(summaryMessage.contains("Internal Error"))
        assertTrue(summaryMessage.contains("500"))

        val stocks = repository.getShariahCompliantStocks()
        assertTrue(stocks.isFailure)
    }

    @Test
    fun repository_propagatesScreeningAndCriteriaFailures() = runBlocking {
        fakeApi.shouldFail = true

        assertTrue(repository.getStockShariahScreening("AIRLINK").isFailure)
        assertTrue(repository.getStockShariahCriteria("AIRLINK").isFailure)
    }

    @Test
    fun purificationSendsDividendIncomeAndFailsOnRejection() = runBlocking {
        val result = repository.calculatePurification("AIRLINK", 1000.0)
        assertTrue(result.isSuccess)
        assertEquals(1000.0, fakeApi.lastDividendIncome!!, 0.001)
        assertEquals(3.8, result.getOrNull()!!.purificationAmount, 0.0001)

        fakeApi.shouldFail = true
        val failure = repository.calculatePurification("AIRLINK", 1000.0)
        assertTrue(failure.isFailure)
        assertEquals("dividend_income: missing", failure.exceptionOrNull()?.message)
    }

    @Test
    fun compliantStocksList_isFilteredByCategoryAndQuery() = runBlocking {
        val all = repository.getShariahCompliantStocks(category = "KMI-30").getOrNull()
        assertNotNull(all)
        assertEquals(3, all!!.size)

        val byCompany = repository.getShariahCompliantStocks(category = "KMI-30", query = "systems").getOrNull()
        assertEquals(listOf("SYS"), byCompany!!.map { it.symbol })

        val bySymbol = repository.getShariahCompliantStocks(category = "KMI-30", query = "air").getOrNull()
        assertEquals(listOf("AIRLINK"), bySymbol!!.map { it.symbol })
    }

    @Test
    fun allStocksCategory_listsTheWholeBoardWithoutInventingAVerdict() = runBlocking {
        val stocks = repository.getShariahCompliantStocks(category = "All Stocks").getOrNull()
        assertNotNull(stocks)
        assertEquals(listOf("SYSTEMS", "HBL"), stocks!!.map { it.symbol })

        // Bulk compliance is only published for KMI-30, so a board row must stay unscreened
        // rather than defaulting to compliant or a 0% purification rate.
        assertTrue(stocks.all { it.isCompliant == null })
        assertTrue(stocks.all { it.purificationRate == null })
        assertTrue(stocks.all { !it.isKmi30 })

        assertEquals(412.5, stocks.first { it.symbol == "SYSTEMS" }.price!!, 0.001)
        assertNull(stocks.first { it.symbol == "HBL" }.price)
    }

    @Test
    fun useCases_executeAgainstTheCapturedPayloads() = runBlocking {
        val kmi = GetKmi30ConstituentsUseCase(repository)()
        assertTrue(kmi.isSuccess)
        assertEquals(3, kmi.getOrNull()?.constituents?.size)

        val screening = GetStockShariahScreeningUseCase(repository)("AIRLINK")
        assertTrue(screening.getOrNull()?.isCompliant == true)

        val unscreened = GetStockShariahScreeningUseCase(repository)("NOTAREALSYM")
        assertFalse(unscreened.getOrNull()?.screeningAvailable == true)

        val criteria = GetStockShariahCriteriaUseCase(repository)("AIRLINK")
        assertEquals(3, criteria.getOrNull()?.criteria?.size)
    }

    @Test
    fun purificationUseCase_rejectsNonPositiveDividendIncome() = runBlocking {
        val purifUseCase = CalculateDividendPurificationUseCase(repository)
        try {
            purifUseCase("AIRLINK", 0.0)
            org.junit.Assert.fail("Expected IllegalArgumentException for zero dividend income")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message?.contains("Dividend income") == true)
        }

        try {
            purifUseCase("AIRLINK", -50.0)
            org.junit.Assert.fail("Expected IllegalArgumentException for negative dividend income")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message?.contains("Dividend income") == true)
        }
    }
}
