package com.fyp.basarattradeinvest.domain.model.market

data class CandleEntry(
    val timestamp: Long,
    val open: Float,
    val high: Float,
    val low: Float,
    val close: Float,
    val volume: Long
)
