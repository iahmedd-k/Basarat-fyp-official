package com.fyp.basarattradeinvest.data.repository

import android.content.Context
import com.fyp.basarattradeinvest.domain.model.market.BenchmarkTrend
import com.google.gson.Gson

/**
 * Last-built benchmark trend, per index and timeframe. The card's line is derived from ~100
 * constituent history calls, so the previous build is painted while a fresh one runs instead of
 * leaving the plot empty for the several seconds that takes.
 */
object BenchmarkTrendCache {

    private const val PREFS_NAME = "basarat_benchmark_trend_cache"
    private const val MAX_AGE_MS = 24 * 60 * 60 * 1000L

    private data class Snapshot(
        val trend: BenchmarkTrend,
        val savedAt: Long
    )

    private val gson = Gson()

    fun keyFor(indexCode: String, timeframe: String): String = "$indexCode|$timeframe"

    fun read(context: Context, indexCode: String, timeframe: String): BenchmarkTrend? {
        val json = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(keyFor(indexCode, timeframe), null) ?: return null
        val snapshot = runCatching { gson.fromJson(json, Snapshot::class.java) }.getOrNull() ?: return null
        val trend = snapshot.trend
        if (trend.points.size < 2) return null
        // The trend carries its own identity so a key written under another index or pill can
        // never surface here.
        if (!trend.indexCode.equals(indexCode, ignoreCase = true) ||
            !trend.timeframe.equals(timeframe, ignoreCase = true)
        ) return null
        if (System.currentTimeMillis() - snapshot.savedAt > MAX_AGE_MS) return null
        return trend
    }

    fun write(context: Context, trend: BenchmarkTrend) {
        if (trend.points.size < 2) return
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit()
            .putString(keyFor(trend.indexCode, trend.timeframe), gson.toJson(Snapshot(trend, System.currentTimeMillis())))
            .apply()
    }
}
