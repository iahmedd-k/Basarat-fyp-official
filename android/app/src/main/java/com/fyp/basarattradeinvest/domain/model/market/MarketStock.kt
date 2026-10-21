package com.fyp.basarattradeinvest.domain.model.market

data class MarketStock(
    val rank: Int,
    val symbol: String,
    val companyName: String,
    val sectorCode: String,
    val price: Double,
    val change: Double,
    val changePercent: Double,
    val volume: String = "",
    val isShariah: Boolean = true
)
