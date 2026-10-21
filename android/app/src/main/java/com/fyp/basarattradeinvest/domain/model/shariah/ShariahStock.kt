package com.fyp.basarattradeinvest.domain.model.shariah

/**
 * One row of the Shariah screening list.
 *
 * Price and change stay null until the live quote layer fills them — the Shariah
 * screening endpoint publishes ratios only, so a row with no quote yet must render
 * as unavailable rather than as a number.
 */
data class ShariahStock(
    val symbol: String,
    val companyName: String,
    val price: Double? = null,
    val changePercent: Double? = null,
    val purificationRate: Double? = null,
    val purificationProvisional: Boolean = false,
    val isCompliant: Boolean? = null,
    val isKmi30: Boolean = true
)
