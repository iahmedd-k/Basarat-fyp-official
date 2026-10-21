package com.fyp.basarattradeinvest.domain.model.market

data class MarketIndex(
    val id: String,
    val name: String,
    val code: String = "",
    val currentPoints: Double,
    val changePoints: Double,
    val changePercent: Double,
    val high: Double = 0.0,
    val low: Double = 0.0,
    val intradayPoints: List<Float> = emptyList()
)
