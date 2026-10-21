package com.fyp.basarattradeinvest.data.remote.dto.stocks

import com.google.gson.annotations.SerializedName

data class TechnicalIndicatorsResponseDto(
    @SerializedName("symbol") val symbol: String? = null,
    @SerializedName("period") val period: Int? = null,
    @SerializedName("overall_signal") val overallSignal: String? = null,
    @SerializedName("summary_message") val summaryMessage: String? = null,
    @SerializedName("signals_breakdown") val signalsBreakdown: SignalsBreakdownDto? = null,
    @SerializedName("summary") val summary: TechnicalSummaryDto? = null,
    @SerializedName("indicators") val indicators: Map<String, List<IndicatorSeriesDto>>? = null
)

data class SignalsBreakdownDto(
    @SerializedName("buy") val buy: Int = 0,
    @SerializedName("neutral") val neutral: Int = 0,
    @SerializedName("sell") val sell: Int = 0
)

data class TechnicalSummaryDto(
    @SerializedName("rsi") val rsi: IndicatorSummaryItemDto? = null,
    @SerializedName("macd") val macd: IndicatorSummaryItemDto? = null,
    @SerializedName("sma") val sma: IndicatorSummaryItemDto? = null,
    @SerializedName("bollinger") val bollinger: IndicatorSummaryItemDto? = null,
    @SerializedName("adx") val adx: IndicatorSummaryItemDto? = null
)

data class IndicatorSummaryItemDto(
    @SerializedName("value") val value: Double? = null,
    @SerializedName("signal") val signal: String? = null,
    @SerializedName("description") val description: String? = null,
    @SerializedName("sma_20") val sma20: Double? = null,
    @SerializedName("sma_50") val sma50: Double? = null,
    @SerializedName("macd_line") val macdLine: Double? = null,
    @SerializedName("signal_line") val signalLine: Double? = null,
    @SerializedName("histogram") val histogram: Double? = null,
    @SerializedName("upper_band") val upperBand: Double? = null,
    @SerializedName("middle_band") val middleBand: Double? = null,
    @SerializedName("lower_band") val lowerBand: Double? = null
)

data class IndicatorSeriesDto(
    @SerializedName("date") val date: String? = null,
    @SerializedName("value") val value: Double? = null
)
