package com.fyp.basarattradeinvest.market

import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.usecase.market.BenchmarkTrendAggregator
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

/**
 * The backend has no index-history endpoint, so the Home benchmark line is computed here from
 * constituents' real daily closes. These tests pin that arithmetic and the window slicing.
 */
class BenchmarkTrendAggregatorTest {

    private val dayMillis = 24L * 60 * 60 * 1000L
    private val anchor = Calendar.getInstance().apply {
        set(2026, Calendar.OCTOBER, 1, 0, 0, 0)
        set(Calendar.MILLISECOND, 0)
    }.timeInMillis

    private fun session(index: Int): Long = anchor + index * dayMillis

    private fun candles(vararg closes: Double): List<CandleEntry> = closes.mapIndexed { i, close ->
        CandleEntry(
            timestamp = session(i),
            open = close.toFloat(),
            high = close.toFloat(),
            low = close.toFloat(),
            close = close.toFloat(),
            volume = 1_000L
        )
    }

    @Test
    fun `first plotted session is the baseline`() {
        val history = mapOf(
            "SYS" to candles(100.0, 110.0, 105.0),
            "LUCK" to candles(200.0, 190.0, 205.0)
        )

        val trend = BenchmarkTrendAggregator.build("KSE100", "3M", history)

        assertEquals(0f, trend?.points?.first()?.changePct ?: 1f, 0f)
    }

    @Test
    fun `equal weight average of constituent growth`() {
        // SYS gains 10%, LUCK loses 5%: (1.10 + 0.95) / 2 - 1 = +2.5%.
        val history = mapOf(
            "SYS" to candles(100.0, 110.0),
            "LUCK" to candles(200.0, 190.0)
        )

        val trend = BenchmarkTrendAggregator.build("KSE100", "3M", history)

        assertEquals(2, trend?.points?.size)
        assertEquals(2, trend?.stockCount)
        assertEquals(2.5f, trend?.points?.last()?.changePct ?: 0f, 0.0001f)
    }

    @Test
    fun `a stock missing a session in the window drops out of the basket`() {
        val history = mapOf(
            "SYS" to candles(100.0, 110.0, 105.0),
            "LUCK" to candles(200.0, 190.0, 205.0),
            // No bar for the third session.
            "OGDC" to listOf(
                CandleEntry(session(0), 50f, 50f, 50f, 50f, 1L),
                CandleEntry(session(1), 55f, 55f, 55f, 55f, 1L)
            )
        )

        val trend = BenchmarkTrendAggregator.build("KSE100", "3M", history)

        assertEquals(2, trend?.stockCount)
        assertEquals(3, trend?.points?.size)
        // SYS 105/100 = +5%, LUCK 205/200 = +2.5% over the same three sessions.
        assertEquals(3.75f, trend?.points?.last()?.changePct ?: 0f, 0.0001f)
    }

    @Test
    fun `a session barely any constituent reports does not veto the window`() {
        val history = buildMap {
            repeat(6) { i -> put("S$i", candles(100.0 + i, 101.0 + i, 102.0 + i, 103.0 + i)) }
            // An ex-date alias that carries one stray session no other constituent traded.
            put("OGDCXD", listOf(CandleEntry(session(4), 50f, 50f, 50f, 50f, 1L)))
        }

        val trend = BenchmarkTrendAggregator.build("KSE100", "3M", history)

        assertEquals(4, trend?.points?.size)
        assertEquals(session(3), trend?.lastSessionTimestamp)
        assertEquals(6, trend?.stockCount)
    }

    @Test
    fun `one constituent is not an index`() {
        val trend = BenchmarkTrendAggregator.build("KSE100", "3M", mapOf("SYS" to candles(100.0, 110.0)))
        assertNull(trend)
    }

    @Test
    fun `empty history yields no trend`() {
        assertNull(BenchmarkTrendAggregator.build("KSE100", "3M", emptyMap()))
    }

    @Test
    fun `1D plots the last five sessions`() {
        val history = mapOf(
            "SYS" to candles(*DoubleArray(12) { 100.0 + it }),
            "LUCK" to candles(*DoubleArray(12) { 200.0 + it })
        )

        val trend = BenchmarkTrendAggregator.build("KSE100", "1D", history)

        assertEquals(5, trend?.points?.size)
        assertEquals(session(7), trend?.firstSessionTimestamp)
        assertEquals(session(11), trend?.lastSessionTimestamp)
    }

    @Test
    fun `1W 1M and 3M cut the window by calendar distance from the latest session`() {
        val sessions = (0 until 200).map { session(it) }

        // Daylight savings can shift a midnight boundary by an hour, so the session counts are
        // bounded rather than pinned to one number.
        val weekly = BenchmarkTrendAggregator.selectWindow("1W", sessions)?.size ?: 0
        assertTrue("expected a week of sessions, got $weekly", weekly in 7..8)
        val monthly = BenchmarkTrendAggregator.selectWindow("1M", sessions)?.size ?: 0
        assertTrue("expected roughly a month of sessions, got $monthly", monthly in 31..32)
        val quarterly = BenchmarkTrendAggregator.selectWindow("3M", sessions)?.size ?: 0
        assertTrue("expected roughly a quarter of sessions, got $quarterly", quarterly in 92..93)
    }

    @Test
    fun `unknown timeframe is rejected rather than defaulted`() {
        val sessions = (0 until 30).map { session(it) }
        assertNull(BenchmarkTrendAggregator.selectWindow("5Y", sessions))
        assertNull(BenchmarkTrendAggregator.selectWindow("1D", emptyList()))
    }

    @Test
    fun `a window with a single session cannot form a line`() {
        val history = mapOf(
            "SYS" to candles(100.0),
            "LUCK" to candles(200.0)
        )
        assertNull(BenchmarkTrendAggregator.build("KSE100", "1D", history))
    }
}
