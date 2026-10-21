package com.fyp.basarattradeinvest.domain.model.stock

data class StockAnalysis(
    val symbol: String,
    val companyName: String,
    val price: Double,
    val changeAmount: Double,
    val changePercent: Double,
    val technical: TechnicalAnalysis,
    val fundamentals: FundamentalMetrics
)

data class TechnicalAnalysis(
    val summary: TechnicalSummary,
    val oscillators: List<TechnicalIndicator>,
    val movingAverages: List<TechnicalIndicator>,
    val pivotPoints: PivotPoints
)

data class TechnicalSummary(
    val overallSignal: TechnicalSignal,
    val buyCount: Int,
    val neutralCount: Int,
    val sellCount: Int,
    val totalCount: Int = buyCount + neutralCount + sellCount
)

data class TechnicalIndicator(
    val name: String,
    val description: String,
    val value: String,
    val signal: TechnicalSignal
)

enum class TechnicalSignal(val label: String) {
    STRONG_BUY("STRONG BUY"),
    BUY("BUY"),
    NEUTRAL("NEUTRAL"),
    SELL("SELL"),
    STRONG_SELL("STRONG SELL")
}

data class PivotPoints(
    val r3: Double,
    val r2: Double,
    val r1: Double,
    val pivot: Double,
    val s1: Double,
    val s2: Double,
    val s3: Double
)

data class FundamentalMetrics(
    // Valuation Multiples
    val peRatio: Double? = null,
    val sectorPeAvg: Double? = null,
    val forwardPe: Double? = null,
    val pbRatio: Double? = null,
    val evEbitda: Double? = null,
    val pegRatio: Double? = null,
    // Profitability & Returns
    val eps: Double? = null,
    val roe: Double? = null,
    val roa: Double? = null,
    val dividendYield: Double? = null,
    val netProfitMargin: Double? = null,
    // Solvency & Financial Health
    val debtToEquity: Double? = null,
    val currentRatio: Double? = null,
    val quickRatio: Double? = null,
    val interestCoverage: Double? = null,
    // Annual Performance
    val revenueTTM: String? = null,
    val revenueGrowthYoY: Double? = null,
    val netIncomeTTM: String? = null,
    val netIncomeGrowthYoY: Double? = null,
    val freeCashFlowTTM: String? = null
)
