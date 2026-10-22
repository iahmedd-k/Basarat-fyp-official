package com.fyp.basarattradeinvest.domain.usecase.market

import com.fyp.basarattradeinvest.domain.model.market.BenchmarkTrend
import com.fyp.basarattradeinvest.domain.model.market.BenchmarkTrendPoint
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import java.util.Calendar
import kotlin.math.ceil

/**
 * Turns constituents' real daily closes into the series the Home benchmark chart plots.
 *
 * The backend exposes no index-history route and every price range it does offer is daily
 * bars, so the line can only be derived from its parts. Each point is the equal-weighted %
 * move of the basket since the window's first session. Equal weight is the only option
 * available: the constituents payload reports weight_pct as 1 and market_cap_m as 0 for
 * every row, so cap weighting would be a guess.
 */
internal object BenchmarkTrendAggregator {

    // The backend's own 1D range returns the last five daily bars, so the proxy matches that.
    private const val SESSIONS_FOR_DAY_RANGE = 5
    private const val MAX_PLOTTED_SESSIONS = 260
    private val WINDOW_DAYS = mapOf("1W" to 7, "1M" to 31, "3M" to 92)

    // Share of constituents that must report a bar for that session to be plottable.
    private const val MIN_SESSION_COVERAGE = 0.5
    private const val MIN_BASKET_SESSIONS = 2

    fun build(
        indexCode: String,
        timeframe: String,
        historyBySymbol: Map<String, List<CandleEntry>>
    ): BenchmarkTrend? {
        if (historyBySymbol.isEmpty()) return null

        val closesBySymbol = historyBySymbol.mapValues { (_, candles) ->
            candles.associate { it.timestamp to it.close }
        }
        val sessions = selectWindow(
            timeframe = timeframe,
            sessions = wellCoveredSessions(closesBySymbol)
        ) ?: return null
        if (sessions.size < 2) return null

        // A stock quoted on every session of the window, with a usable opening price. Dropping
        // halted or newly listed names keeps the average over a fixed basket instead of letting
        // the line bend where a constituent simply has no bar.
        val basket = closesBySymbol.filter { (_, closes) ->
            val base = closes[sessions.first()] ?: return@filter false
            base > 0f && sessions.all { closes.containsKey(it) }
        }
        if (basket.size < 2) return null

        val baseline = sessions.first()
        val points = sessions.map { session ->
            var growthSum = 0.0
            basket.forEach { (_, closes) ->
                val base = closes.getValue(baseline).toDouble()
                growthSum += closes.getValue(session).toDouble() / base
            }
            BenchmarkTrendPoint(
                timestamp = session,
                changePct = ((growthSum / basket.size) - 1.0).toFloat() * 100f
            )
        }

        return BenchmarkTrend(
            indexCode = indexCode,
            timeframe = timeframe,
            points = points,
            stockCount = basket.size,
            firstSessionTimestamp = sessions.first(),
            lastSessionTimestamp = sessions.last()
        )
    }

    /**
     * Sessions at least half of the constituents actually report. Ex-date aliases arrive in the
     * constituents list carrying two or three bars for the whole year, and the feed occasionally
     * drops a session for most symbols; kept in the window they make the all-sessions rule above
     * unmeetable, which is why the 3M pill used to resolve to an empty basket and plot nothing.
     */
    private fun wellCoveredSessions(closesBySymbol: Map<String, Map<Long, Float>>): List<Long> {
        if (closesBySymbol.isEmpty()) return emptyList()
        val floor = maxOf(MIN_BASKET_SESSIONS, ceil(closesBySymbol.size * MIN_SESSION_COVERAGE).toInt())
        val coverage = HashMap<Long, Int>()
        closesBySymbol.values.forEach { closes ->
            closes.keys.forEach { session -> coverage[session] = (coverage[session] ?: 0) + 1 }
        }
        return coverage.filter { (_, count) -> count >= floor }.keys.sorted()
    }

    /** The real trading sessions to plot for [timeframe], or null when the range is unknown. */
    fun selectWindow(timeframe: String, sessions: List<Long>): List<Long>? {
        if (sessions.isEmpty()) return null
        val windowed = when (timeframe.uppercase()) {
            "1D" -> sessions.takeLast(SESSIONS_FOR_DAY_RANGE)
            else -> {
                val days = WINDOW_DAYS[timeframe.uppercase()] ?: return null
                val cutoff = subtractDays(sessions.last(), days)
                sessions.filter { it >= cutoff }
            }
        }
        return windowed.takeLast(MAX_PLOTTED_SESSIONS).ifEmpty { null }
    }

    private fun subtractDays(timestamp: Long, days: Int): Long =
        Calendar.getInstance().apply {
            timeInMillis = timestamp
            add(Calendar.DAY_OF_YEAR, -days)
        }.timeInMillis
}
