package com.fyp.basarattradeinvest.risk

import com.fyp.basarattradeinvest.data.mapper.RiskDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.RiskApiService
import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.MonteCarloResultResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.RiskVaRResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.risk.StressTestResponseDto
import com.fyp.basarattradeinvest.data.repository.RiskRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloJob
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloResult
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloStats
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.risk.StressTestResult
import com.fyp.basarattradeinvest.domain.repository.RiskRepository
import com.fyp.basarattradeinvest.domain.usecase.risk.GetMonteCarloResultUseCase
import com.fyp.basarattradeinvest.domain.usecase.risk.GetPortfolioVaRUseCase
import com.fyp.basarattradeinvest.domain.usecase.risk.GetStressTestScenarioUseCase
import com.fyp.basarattradeinvest.domain.usecase.risk.StartMonteCarloSimulationUseCase
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class RiskModuleUnitTest {

    private val gson = Gson()

    // 1. DTO Deserialization Test
    @Test
    fun testRiskVaRResponseDtoDeserialization() {
        val json = """
            {
                "confidence": 95,
                "horizon": "1D",
                "var_value": -0.0234,
                "cvar_value": -0.0351,
                "method": "historical_simulation",
                "num_observations": 252,
                "annualized_volatility": 0.1856
            }
        """.trimIndent()

        val dto = gson.fromJson(json, RiskVaRResponseDto::class.java)
        assertEquals(95, dto.confidence)
        assertEquals("1D", dto.horizon)
        assertEquals(-0.0234, dto.varValue!!, 0.0001)
        assertEquals(-0.0351, dto.cvarValue!!, 0.0001)
        assertEquals("historical_simulation", dto.method)
        assertEquals(252, dto.numObservations)
        assertEquals(0.1856, dto.annualizedVolatility!!, 0.0001)
    }

    @Test
    fun testMonteCarloDtosDeserialization() {
        val jsonJob = """
            {
                "job_id": "mc_task_999",
                "status": "pending",
                "num_simulations": 1000,
                "horizon_days": 30,
                "message": "Simulation queued"
            }
        """.trimIndent()

        val jobDto = gson.fromJson(jsonJob, MonteCarloResponseDto::class.java)
        assertEquals("mc_task_999", jobDto.jobId)
        assertEquals("pending", jobDto.status)
        assertEquals(1000, jobDto.numSimulations)
        assertEquals(30, jobDto.horizonDays)

        val jsonResult = """
            {
                "job_id": "mc_task_999",
                "status": "completed",
                "num_simulations": 1000,
                "horizon_days": 30,
                "percentiles": {
                    "p5": -0.085,
                    "p50": 0.032,
                    "p95": 0.145
                },
                "stats": {
                    "mean_return": 0.035,
                    "prob_loss": 0.38,
                    "max_drawdown": -0.19,
                    "best_case": 0.25
                }
            }
        """.trimIndent()

        val resultDto = gson.fromJson(jsonResult, MonteCarloResultResponseDto::class.java)
        assertEquals("mc_task_999", resultDto.jobId)
        assertEquals("completed", resultDto.status)
        assertEquals(-0.085, resultDto.percentiles!!["p5"]!!, 0.001)
        assertEquals(0.035, (resultDto.stats!!["mean_return"] as Number).toDouble(), 0.001)
    }

    @Test
    fun testStressTestDtoDeserialization() {
        val json = """
            {
                "scenario": "2008_crash",
                "name": "2008 Global Financial Crisis",
                "description": "Simulates 2008 Lehman collapse",
                "portfolio_impact": -0.45,
                "portfolio_impact_value": -450000.0,
                "worst_case_loss": -0.60,
                "volatility_multiplier": 2.5,
                "recovery_days": 540,
                "current_value": 1000000.0,
                "stressed_value": 550000.0,
                "holding_impacts": [
                    {
                        "symbol": "LUCK",
                        "impact": -0.40,
                        "impact_value": -120000.0,
                        "current_value": 300000.0,
                        "stressed_value": 180000.0
                    }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, StressTestResponseDto::class.java)
        assertEquals("2008_crash", dto.scenario)
        assertEquals(-0.45, dto.portfolioImpact, 0.001)
        assertEquals(-450000.0, dto.portfolioImpactValue, 0.1)
        assertEquals(1, dto.holdingImpacts?.size)
    }

    // 2. Mapper Tests
    @Test
    fun testRiskDtoMapper() {
        val varDto = RiskVaRResponseDto(
            confidence = 99,
            horizon = "1W",
            varValue = -0.052,
            cvarValue = -0.071,
            method = "historical_simulation",
            numObservations = 500,
            annualizedVolatility = 0.22
        )
        val domainVaR = RiskDtoMapper.mapVaR(varDto)
        assertEquals(99, domainVaR.confidence)
        assertEquals("1W", domainVaR.horizon)
        assertEquals(-0.052, domainVaR.varValue, 0.0001)
        assertEquals(500, domainVaR.numObservations)

        val mcResultDto = MonteCarloResultResponseDto(
            jobId = "test_job_1",
            status = "completed",
            numSimulations = 1000,
            horizonDays = 30,
            percentiles = mapOf("p5" to -0.07, "p50" to 0.04),
            stats = mapOf("mean_return" to 0.038, "prob_loss" to 0.32)
        )
        val domainMC = RiskDtoMapper.mapMonteCarloResult(mcResultDto)
        assertEquals("test_job_1", domainMC.jobId)
        assertEquals("COMPLETED", domainMC.status.uppercase())
        assertEquals(2, domainMC.percentiles.size)
        assertEquals(0.038, domainMC.stats.meanReturn!!, 0.001)
        assertEquals(0.32, domainMC.stats.probLoss!!, 0.001)
    }

    // 3. Repository Success and 401 Error Handling Tests
    @Test
    fun testRepositorySuccess() = runBlocking {
        val fakeApiService = object : RiskApiService {
            override suspend fun getValueAtRisk(confidence: Int?, horizon: String?): Response<RiskVaRResponseDto> {
                val dto = RiskVaRResponseDto(confidence = confidence ?: 95, horizon = horizon ?: "1D", varValue = -0.025)
                return Response.success(dto)
            }

            override suspend fun startMonteCarloSimulation(request: MonteCarloRequestDto): Response<MonteCarloResponseDto> {
                val dto = MonteCarloResponseDto(jobId = "sim_123", status = "pending", numSimulations = request.numSimulations, horizonDays = request.horizonDays)
                return Response.success(dto)
            }

            override suspend fun getMonteCarloResult(taskId: String): Response<MonteCarloResultResponseDto> {
                val dto = MonteCarloResultResponseDto(jobId = taskId, status = "completed")
                return Response.success(dto)
            }

            override suspend fun getStressTest(scenario: String?): Response<StressTestResponseDto> {
                val dto = StressTestResponseDto(
                    scenario = scenario ?: "2008_crash",
                    name = "2008 Crash",
                    description = "Test description",
                    portfolioImpact = -0.35,
                    portfolioImpactValue = -350000.0,
                    worstCaseLoss = -0.5,
                    volatilityMultiplier = 2.0,
                    recoveryDays = 300,
                    currentValue = 1000000.0,
                    stressedValue = 650000.0
                )
                return Response.success(dto)
            }
        }

        val repository = RiskRepositoryImpl(apiService = fakeApiService)

        val varResult = repository.getValueAtRisk(95, "1D")
        assertTrue(varResult.isSuccess)
        assertEquals(-0.025, varResult.getOrThrow().varValue, 0.001)

        val mcStartResult = repository.startMonteCarloSimulation(1000, 30)
        assertTrue(mcStartResult.isSuccess)
        assertEquals("sim_123", mcStartResult.getOrThrow().jobId)

        val mcResult = repository.getMonteCarloResult("sim_123")
        assertTrue(mcResult.isSuccess)
        assertEquals("completed", mcResult.getOrThrow().status)

        val stressResult = repository.getStressTest("2008_crash")
        assertTrue(stressResult.isSuccess)
        assertEquals(-0.35, stressResult.getOrThrow().portfolioImpact, 0.001)
    }

    @Test
    fun testRepository401UnauthorizedHandling() = runBlocking {
        val fakeApiService = object : RiskApiService {
            override suspend fun getValueAtRisk(confidence: Int?, horizon: String?): Response<RiskVaRResponseDto> {
                val errorJson = "{\"code\":\"UNAUTHORIZED\",\"message\":\"Not authenticated\"}"
                val errorBody = errorJson.toResponseBody("application/json".toMediaTypeOrNull())
                return Response.error(401, errorBody)
            }

            override suspend fun startMonteCarloSimulation(request: MonteCarloRequestDto): Response<MonteCarloResponseDto> {
                val errorJson = "{\"code\":\"UNAUTHORIZED\",\"message\":\"Not authenticated\"}"
                val errorBody = errorJson.toResponseBody("application/json".toMediaTypeOrNull())
                return Response.error(401, errorBody)
            }

            override suspend fun getMonteCarloResult(taskId: String): Response<MonteCarloResultResponseDto> {
                val errorJson = "{\"code\":\"UNAUTHORIZED\",\"message\":\"Not authenticated\"}"
                val errorBody = errorJson.toResponseBody("application/json".toMediaTypeOrNull())
                return Response.error(401, errorBody)
            }

            override suspend fun getStressTest(scenario: String?): Response<StressTestResponseDto> {
                val errorJson = "{\"code\":\"UNAUTHORIZED\",\"message\":\"Not authenticated\"}"
                val errorBody = errorJson.toResponseBody("application/json".toMediaTypeOrNull())
                return Response.error(401, errorBody)
            }
        }

        val repository = RiskRepositoryImpl(apiService = fakeApiService)
        val varResult = repository.getValueAtRisk(95, "1D")
        assertTrue(varResult.isFailure)
        assertEquals("Not authenticated", varResult.exceptionOrNull()?.message)
    }

    // 4. Use Cases Tests
    @Test
    fun testUseCases() = runBlocking {
        val fakeRepository = object : RiskRepository {
            override suspend fun getValueAtRisk(confidence: Int?, horizon: String?): Result<PortfolioVaR> {
                return Result.success(PortfolioVaR(confidence = confidence ?: 95, horizon = horizon ?: "1D", varValue = -0.02, cvarValue = -0.03, method = "historical_simulation", numObservations = 252, annualizedVolatility = 0.15))
            }

            override suspend fun startMonteCarloSimulation(numSimulations: Int, horizonDays: Int): Result<MonteCarloJob> {
                return Result.success(MonteCarloJob(jobId = "job_456", status = "pending", numSimulations = numSimulations, horizonDays = horizonDays, message = null))
            }

            override suspend fun getMonteCarloResult(taskId: String): Result<MonteCarloResult> {
                return Result.success(
                    MonteCarloResult(
                        jobId = taskId,
                        status = "completed",
                        numSimulations = 1000,
                        horizonDays = 30,
                        params = emptyMap(),
                        percentiles = emptyList(),
                        stats = MonteCarloStats(meanReturn = 0.05, stdReturn = 0.1, probLoss = 0.25, maxDrawdown = -0.15, bestCase = 0.3),
                        pathsSample = emptyList(),
                        error = null,
                        completedAt = null
                    )
                )
            }

            override suspend fun getStressTest(scenario: String?): Result<StressTestResult> {
                return Result.success(
                    StressTestResult(
                        scenario = scenario ?: "2008_crash",
                        name = "2008 Crash",
                        description = "GFC",
                        portfolioImpact = -0.45,
                        portfolioImpactValue = -450000.0,
                        worstCaseLoss = -0.6,
                        volatilityMultiplier = 2.5,
                        recoveryDays = 540,
                        currentValue = 1000000.0,
                        stressedValue = 550000.0,
                        holdingImpacts = emptyList()
                    )
                )
            }
        }

        val getVaRUseCase = GetPortfolioVaRUseCase(fakeRepository)
        val startMCUseCase = StartMonteCarloSimulationUseCase(fakeRepository)
        val getMCResultUseCase = GetMonteCarloResultUseCase(fakeRepository)
        val getStressUseCase = GetStressTestScenarioUseCase(fakeRepository)

        val vaR = getVaRUseCase(95, "1D").getOrThrow()
        assertEquals(-0.02, vaR.varValue, 0.001)

        val job = startMCUseCase(1000, 30).getOrThrow()
        assertEquals("job_456", job.jobId)

        val mcResult = getMCResultUseCase("job_456").getOrThrow()
        assertEquals("completed", mcResult.status)

        val stress = getStressUseCase("2008_crash").getOrThrow()
        assertEquals(-0.45, stress.portfolioImpact, 0.001)
    }
}
