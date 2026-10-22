package com.fyp.basarattradeinvest.domain.model.market

data class MarketOverview(
    val tradedValue: String,
    val tradedVolume: String,
    val totalTrades: String,
    val upCount: Int,
    val unchangedCount: Int,
    val downCount: Int,
    val totalStocks: Int
)
