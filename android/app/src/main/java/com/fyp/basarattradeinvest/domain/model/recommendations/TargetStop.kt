package com.fyp.basarattradeinvest.domain.model.recommendations

data class TargetStop(
    val symbol: String,
    val currentPrice: Double?,
    val targetPrice: Double?,
    val stopLoss: Double?,
    val expectedRange: ExpectedPriceRange?,
    val method: String,
    val atr14: Double?,
    val riskTolerance: String,
    val upsidePct: Double?,
    val downsidePct: Double?
)
