package com.fyp.basarattradeinvest.market

import com.fyp.basarattradeinvest.data.remote.dto.market.GainersResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.IndexConstituentsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.IndicesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.LosersResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.SentimentOverviewDto
import com.fyp.basarattradeinvest.data.remote.dto.market.VolumeSpikesResponseDto
import com.fyp.basarattradeinvest.data.remote.mapper.toDomain
import com.fyp.basarattradeinvest.data.repository.MarketRepositoryImpl
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MarketModuleUnitTest {

    private val gson = Gson()

    @Test
    fun testIndicesResponseDtoMapping() {
        val json = """
            {
                "indices": [
                    {
                        "index": "KSE-100",
                        "code": "KSE100",
                        "current": 85421.32,
                        "change": -142.70,
                        "change_pct": -0.17,
                        "high": 85650.0,
                        "low": 85300.0
                    },
                    {
                        "index": "KSE-30",
                        "code": "KSE30",
                        "current": 26840.15,
                        "change": 78.40,
                        "change_pct": 0.29,
                        "high": 26900.0,
                        "low": 26750.0
                    }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, IndicesResponseDto::class.java)
        assertNotNull(dto.indices)
        assertEquals(2, dto.indices!!.size)

        val domain = dto.indices!!.map { it.toDomain() }
        assertEquals("KSE-100", domain[0].name)
        assertEquals("KSE100", domain[0].code)
        assertEquals(85421.32, domain[0].currentPoints, 0.001)
        assertEquals(-142.70, domain[0].changePoints, 0.001)
        assertEquals(-0.17, domain[0].changePercent, 0.001)
        assertEquals(85650.0, domain[0].high, 0.001)
        assertEquals(85300.0, domain[0].low, 0.001)

        assertEquals("KSE-30", domain[1].name)
        assertEquals(26840.15, domain[1].currentPoints, 0.001)
    }

    @Test
    fun testIndexConstituentsResponseDtoMapping() {
        val json = """
            {
                "index": "KMI-30",
                "code": "KMI30",
                "shariah_compliant": true,
                "constituents": [
                    {
                        "symbol": "OGDC",
                        "name": "Oil & Gas Development Co",
                        "ldcp": 140.0,
                        "current": 142.50,
                        "change": 2.50,
                        "change_pct": 1.79,
                        "weight_pct": 8.4,
                        "index_points": 450.2,
                        "volume": 12500000,
                        "freefloat_m": 4500.0,
                        "market_cap_m": 25000.0
                    }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, IndexConstituentsResponseDto::class.java)
        val domain = dto.toDomain()

        assertEquals("KMI-30", domain.index)
        assertEquals("KMI30", domain.code)
        assertEquals(true, domain.isShariahCompliant)
        assertEquals(1, domain.constituents.size)

        val first = domain.constituents[0]
        assertEquals("OGDC", first.symbol)
        assertEquals("Oil & Gas Development Co", first.name)
        assertEquals(142.50, first.current, 0.001)
        assertEquals(2.50, first.change, 0.001)
        assertEquals(1.79, first.changePct, 0.001)
        assertEquals(8.4, first.weightPct, 0.001)
        assertEquals(450.2, first.indexPoints, 0.001)
        assertEquals(12500000L, first.volume)
    }

    @Test
    fun testGainersResponseDtoMapping() {
        val json = """
            {
                "gainers": [
                    {
                        "symbol": "ARMAH",
                        "sector": "Commercial Banks",
                        "ldcp": 65.35,
                        "open": 66.0,
                        "high": 71.85,
                        "low": 65.5,
                        "current": 71.85,
                        "change": 6.50,
                        "change_pct": 9.95,
                        "volume": 4200000
                    }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, GainersResponseDto::class.java)
        assertNotNull(dto.gainers)
        val domain = dto.gainers!!.mapIndexed { index, item -> item.toDomain(index + 1) }

        assertEquals(1, domain.size)
        assertEquals(1, domain[0].rank)
        assertEquals("ARMAH", domain[0].symbol)
        assertEquals("Commercial Banks", domain[0].sectorCode)
        assertEquals(71.85, domain[0].price, 0.001)
        assertEquals(9.95, domain[0].changePercent, 0.001)
        assertEquals("4.20M", domain[0].volume)
    }

    @Test
    fun testLosersResponseDtoMapping() {
        val json = """
            {
                "losers": [
                    {
                        "symbol": "KEL",
                        "sector": "Power Generation",
                        "ldcp": 4.50,
                        "open": 4.50,
                        "high": 4.55,
                        "low": 4.10,
                        "current": 4.12,
                        "change": -0.38,
                        "change_pct": -8.44,
                        "volume": 35200000
                    }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, LosersResponseDto::class.java)
        val domain = dto.losers!!.mapIndexed { idx, it -> it.toDomain(idx + 1) }

        assertEquals(1, domain.size)
        assertEquals("KEL", domain[0].symbol)
        assertEquals(4.12, domain[0].price, 0.001)
        assertEquals(-8.44, domain[0].changePercent, 0.001)
        assertEquals("35.20M", domain[0].volume)
    }

    @Test
    fun testVolumeSpikesResponseDtoMapping() {
        val json = """
            {
                "volume_spikes": [
                    {
                        "symbol": "WTL",
                        "sector": "Technology",
                        "ldcp": 1.33,
                        "open": 1.35,
                        "high": 1.48,
                        "low": 1.32,
                        "current": 1.45,
                        "change": 0.12,
                        "change_pct": 9.02,
                        "volume": 42100000
                    }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, VolumeSpikesResponseDto::class.java)
        val domain = dto.volumeSpikes!!.mapIndexed { idx, it -> it.toDomain(idx + 1) }

        assertEquals(1, domain.size)
        assertEquals("WTL", domain[0].symbol)
        assertEquals(1.45, domain[0].price, 0.001)
        assertEquals("42.10M", domain[0].volume)
    }

    @Test
    fun testSentimentOverviewDtoMapping() {
        val json = """
            {
                "market_mood": "Bullish",
                "advancing": 195,
                "declining": 137,
                "unchanged": 42,
                "advance_decline_ratio": 1.42,
                "gainers_pct": 52.1,
                "losers_pct": 36.6,
                "sector_performance": [
                    {
                        "sector": "Commercial Banks",
                        "avg_change_pct": 1.45,
                        "companies": 20
                    }
                ],
                "top_movers": [
                    {
                        "symbol": "OGDC",
                        "sector": "Oil & Gas",
                        "ldcp": 140.0,
                        "open": 141.0,
                        "high": 144.0,
                        "low": 140.5,
                        "current": 142.5,
                        "change": 2.5,
                        "change_pct": 1.79,
                        "volume": 12500000
                    }
                ]
            }
        """.trimIndent()

        val dto = gson.fromJson(json, SentimentOverviewDto::class.java)
        val domain = dto.toDomain()

        assertEquals("Bullish", domain.sentimentLabel)
        assertEquals(195, domain.advancing)
        assertEquals(137, domain.declining)
        assertEquals(42, domain.unchanged)
        assertEquals(1.42, domain.advanceDeclineRatio, 0.001)
        assertEquals(52, domain.positivePercent)
        assertEquals(36, domain.negativePercent)
        assertTrue(domain.overallScore in 0..100)

        assertNotNull(dto.sectorPerformance)
        val sectors = dto.sectorPerformance!!.map { it.toDomain() }
        assertEquals(1, sectors.size)
        assertEquals("Commercial Banks", sectors[0].sectorName)
        assertEquals(1.45, sectors[0].changePercent, 0.001)
        assertTrue(sectors[0].isPositive)
    }

    @Test
    fun testMarketRepositoryFallbackMode() = runBlocking {
        MarketRepositoryImpl.IS_MOCK_MODE = true
        val repo = MarketRepositoryImpl()

        val indicesResult = repo.getMarketIndices()
        assertTrue(indicesResult.isSuccess)
        val indices = indicesResult.getOrThrow()
        assertEquals(3, indices.size)
        assertEquals("KSE-100", indices[0].name)
        assertEquals("KSE-30", indices[1].name)
        assertEquals("KMI-30", indices[2].name)

        val kse100Result = repo.getKse100Constituents()
        assertTrue(kse100Result.isSuccess)
        assertEquals(5, kse100Result.getOrThrow().constituents.size)

        val gainersResult = repo.getTopGainers()
        assertTrue(gainersResult.isSuccess)
        assertTrue(gainersResult.getOrThrow().isNotEmpty())

        val losersResult = repo.getTopLosers()
        assertTrue(losersResult.isSuccess)
        assertTrue(losersResult.getOrThrow().isNotEmpty())

        val volumeResult = repo.getVolumeSpikes()
        assertTrue(volumeResult.isSuccess)
        assertTrue(volumeResult.getOrThrow().isNotEmpty())

        val sentimentResult = repo.getMarketSentimentOverview()
        assertTrue(sentimentResult.isSuccess)
        assertEquals("Bullish", sentimentResult.getOrThrow().sentimentLabel)

        // Reset for production
        MarketRepositoryImpl.IS_MOCK_MODE = false
    }
}
