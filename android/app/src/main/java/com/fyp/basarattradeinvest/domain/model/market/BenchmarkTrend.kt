package com.fyp.basarattradeinvest.domain.model.market

/** One plotted session of the benchmark trend, expressed as % move from the window's first close. */
data class BenchmarkTrendPoint(
    val timestamp: Long,
    val changePct: Float
)

/**
 * The Home benchmark line. It is an equal-weighted proxy computed from constituent closes,
 * not an official index level, so [stockCount] and the session range travel with it and the
 * UI can state its provenance.
 */
data class BenchmarkTrend(
    val indexCode: String,
    val timeframe: String,
    val points: List<BenchmarkTrendPoint>,
    val stockCount: Int,
    val firstSessionTimestamp: Long,
    val lastSessionTimestamp: Long
)
