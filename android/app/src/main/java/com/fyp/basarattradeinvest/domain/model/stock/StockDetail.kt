package com.fyp.basarattradeinvest.domain.model.stock

data class StockDetail(
    val symbol: String,
    val code: String,
    val companyName: String,
    val sector: String,
    val price: Double,
    val changeAmount: Double,
    val changePercent: Double,
    val marketStatus: String,       // "Open" / "Closed"
    val lastUpdated: String,        // "14/09-15:20:00"
    val isShariah: Boolean = true,
    val hasDividend: Boolean = true,
    val isCompliant: Boolean = true,
    // Key Stats
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val volume: Long,
    val avgVolume: Long,
    val high52Week: Double,
    val low52Week: Double,
    val marketCap: String,
    val pe: Double,
    val eps: Double
)
