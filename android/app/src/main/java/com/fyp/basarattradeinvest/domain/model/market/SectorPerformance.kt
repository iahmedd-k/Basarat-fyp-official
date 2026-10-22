package com.fyp.basarattradeinvest.domain.model.market

data class SectorPerformance(
    val id: String,
    val sectorName: String,
    val changePercent: Double,
    val volume: String,
    val isPositive: Boolean
)
