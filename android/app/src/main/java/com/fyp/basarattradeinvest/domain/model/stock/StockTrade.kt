package com.fyp.basarattradeinvest.domain.model.stock

data class StockTrade(
    val time: String,
    val price: Double,
    val volume: Long,
    val type: String  // "BUY" or "SELL"
)
