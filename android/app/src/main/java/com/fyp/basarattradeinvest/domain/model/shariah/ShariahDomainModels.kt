package com.fyp.basarattradeinvest.domain.model.shariah

data class Kmi30IndexSummary(
    val index: String?,
    val totalConstituents: Int,
    val asOf: String?,
    val isStale: Boolean,
    val constituents: List<Kmi30Constituent>
)

/**
 * One KMI-30 Shariah screening row. The screening endpoint publishes ratios only;
 * price and change are attached by the live quote layer, never by this model.
 */
data class Kmi30Constituent(
    val symbol: String,
    val name: String,
    val isCompliant: Boolean?,
    val debtRatio: Double?,
    val interestIncomeRatio: Double?,
    val dataAsOf: String?,
    val purificationRateProvisional: Boolean
)

data class StockShariahCompliance(
    val symbol: String,
    val screeningAvailable: Boolean,
    val isCompliant: Boolean,
    val overallScore: Double?,
    val screeningMethod: String?,
    val screenedAt: String?,
    val dataAsOf: String?,
    val dataIsStale: Boolean,
    val sector: String?,
    val purificationRate: Double?,
    val purificationRateProvisional: Boolean,
    val complianceSummary: String?
)

data class StockShariahCriteria(
    val symbol: String,
    val screeningAvailable: Boolean,
    val isCompliant: Boolean,
    val criteria: List<ShariahCriterionItem>
)

data class ShariahCriterionItem(
    val name: String,
    val threshold: Double?,
    val value: Double?,
    val passed: Boolean?,
    val description: String?,
    val exception: String?
)

data class DividendPurificationResult(
    val symbol: String,
    val dividendIncome: Double,
    val purificationAmount: Double,
    val purificationRate: Double,
    val notes: String?,
    val rateIsProvisional: Boolean
)
