package com.fyp.basarattradeinvest.domain.model.market

data class IndexConstituent(
    val symbol: String,
    val name: String,
    val ldcp: Double,
    val current: Double,
    val change: Double,
    val changePct: Double,
    val weightPct: Double,
    val indexPoints: Double,
    val volume: Long,
    val freeFloatM: Double,
    val marketCapM: Double
)

data class IndexConstituents(
    val index: String,
    val code: String,
    val isShariahCompliant: Boolean?,
    val constituents: List<IndexConstituent>
)
