package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.stocks.FundamentalsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.PriceBarDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.PriceHistoryResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.StockOverviewDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.StockSearchResultDto
import com.fyp.basarattradeinvest.data.remote.dto.stocks.TechnicalIndicatorsResponseDto
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.FundamentalMetrics
import com.fyp.basarattradeinvest.domain.model.stock.PivotPoints
import com.fyp.basarattradeinvest.domain.model.stock.StockDetail
import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalIndicator
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalSignal
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalSummary
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object StocksDtoMapper {

    fun mapSearchResult(dto: StockSearchResultDto): StockSearchResult {
        val symbol = dto.symbol.orEmpty().uppercase()
        return StockSearchResult(
            symbol = symbol,
            name = dto.name ?: "$symbol Corporation",
            sector = dto.sector ?: "General"
        )
    }

    fun mapOverviewToStockDetail(dto: StockOverviewDto): StockDetail {
        val symbol = dto.symbol.orEmpty().uppercase()
        val currentLtp = dto.ltp ?: 0.0
        val change = dto.change ?: 0.0
        val changePct = dto.changePct ?: 0.0
        val dayLow = dto.dayRange?.low ?: currentLtp
        val dayHigh = dto.dayRange?.high ?: currentLtp
        val volume = dto.volume ?: 0L
        val formattedMarketCap = if (dto.marketCapM != null) {
            String.format(Locale.US, "%.1fM", dto.marketCapM)
        } else if (dto.marketCap != null) {
            String.format(Locale.US, "%.1fB", dto.marketCap / 1_000_000_000.0)
        } else {
            "N/A"
        }

        val currentTime = SimpleDateFormat("dd/MM-HH:mm:ss", Locale.US).format(Date())

        return StockDetail(
            symbol = symbol,
            code = symbol,
            companyName = dto.name ?: "$symbol Limited",
            sector = dto.sector ?: "General",
            price = currentLtp,
            changeAmount = change,
            changePercent = changePct,
            marketStatus = "Active",
            lastUpdated = currentTime,
            isShariah = true,
            hasDividend = true,
            isCompliant = true,
            open = dto.ldcp ?: currentLtp,
            high = dayHigh,
            low = dayLow,
            close = currentLtp,
            volume = volume,
            avgVolume = volume,
            high52Week = dayHigh * 1.2,
            low52Week = dayLow * 0.8,
            marketCap = formattedMarketCap,
            pe = dto.peRatio ?: 0.0,
            eps = if (dto.peRatio != null && dto.peRatio > 0) currentLtp / dto.peRatio else 0.0
        )
    }

    fun mapPriceHistoryToCandles(dto: PriceHistoryResponseDto): List<CandleEntry> {
        val bars = dto.bars.orEmpty()
        if (bars.isEmpty()) return emptyList()

        val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.US)

        return bars.map { bar ->
            val timestamp = try {
                dateFormat.parse(bar.date.orEmpty())?.time ?: System.currentTimeMillis()
            } catch (e: Exception) {
                System.currentTimeMillis()
            }
            CandleEntry(
                timestamp = timestamp,
                open = bar.open.toFloat(),
                high = bar.high.toFloat(),
                low = bar.low.toFloat(),
                close = bar.close.toFloat(),
                volume = bar.volume
            )
        }
    }

    fun mapTechnicalIndicators(dto: TechnicalIndicatorsResponseDto): TechnicalAnalysis {
        val overallSig = when (dto.overallSignal?.uppercase()) {
            "STRONG_BUY", "STRONG BUY" -> TechnicalSignal.STRONG_BUY
            "BUY" -> TechnicalSignal.BUY
            "SELL" -> TechnicalSignal.SELL
            "STRONG_SELL", "STRONG SELL" -> TechnicalSignal.STRONG_SELL
            else -> TechnicalSignal.NEUTRAL
        }

        val buyCount = dto.signalsBreakdown?.buy ?: 0
        val neutralCount = dto.signalsBreakdown?.neutral ?: 0
        val sellCount = dto.signalsBreakdown?.sell ?: 0

        val oscillators = mutableListOf<TechnicalIndicator>()
        val summary = dto.summary

        summary?.rsi?.let {
            oscillators.add(
                TechnicalIndicator(
                    name = "RSI (14)",
                    description = it.description ?: "Relative Strength Index",
                    value = if (it.value != null) String.format(Locale.US, "%.1f", it.value) else "N/A",
                    signal = parseSignal(it.signal)
                )
            )
        }

        summary?.macd?.let {
            oscillators.add(
                TechnicalIndicator(
                    name = "MACD (12,26,9)",
                    description = it.description ?: "Moving Average Convergence Divergence",
                    value = if (it.value != null) String.format(Locale.US, "%.2f", it.value) else "N/A",
                    signal = parseSignal(it.signal)
                )
            )
        }

        summary?.adx?.let {
            oscillators.add(
                TechnicalIndicator(
                    name = "ADX (14)",
                    description = it.description ?: "Average Directional Index",
                    value = if (it.value != null) String.format(Locale.US, "%.1f", it.value) else "N/A",
                    signal = parseSignal(it.signal)
                )
            )
        }

        summary?.bollinger?.let {
            oscillators.add(
                TechnicalIndicator(
                    name = "Bollinger Bands",
                    description = it.description ?: "Volatility Bands",
                    value = if (it.middleBand != null) String.format(Locale.US, "%.1f", it.middleBand) else "N/A",
                    signal = parseSignal(it.signal)
                )
            )
        }

        val movingAverages = mutableListOf<TechnicalIndicator>()
        summary?.sma?.let {
            movingAverages.add(
                TechnicalIndicator(
                    name = "SMA (20)",
                    description = it.description ?: "Simple Moving Average",
                    value = if (it.sma20 != null) String.format(Locale.US, "%.2f", it.sma20) else (it.value?.toString() ?: "N/A"),
                    signal = parseSignal(it.signal)
                )
            )
        }

        return TechnicalAnalysis(
            summary = TechnicalSummary(
                overallSignal = overallSig,
                buyCount = buyCount,
                neutralCount = neutralCount,
                sellCount = sellCount
            ),
            oscillators = oscillators,
            movingAverages = movingAverages,
            pivotPoints = PivotPoints(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        )
    }

    fun mapFundamentals(dto: FundamentalsResponseDto): FundamentalMetrics {
        val ratios = dto.ratios ?: dto.financialRatios
        val extras = dto.extras
        val equity = dto.equityProfile
        val shareStructure = dto.shareStructure
        val valuation = dto.valuation
        val profitability = dto.profitability
        val growth = dto.growth

        // Helper to extract metric values from the "metrics" list by key or name
        val metricsMap = dto.metrics?.associate { 
            (it.key ?: it.name ?: "").uppercase().trim() to it 
        } ?: emptyMap()

        val pe = valuation?.peRatio
            ?: ratios?.peRatio
            ?: metricsMap["P/E RATIO"]?.getValueAsDouble()
            ?: metricsMap["PE RATIO"]?.getValueAsDouble()
            ?: metricsMap["PE"]?.getValueAsDouble()

        val peg = valuation?.pegRatio
            ?: ratios?.pegRatio
            ?: metricsMap["PEG RATIO"]?.getValueAsDouble()

        val epsVal = profitability?.eps
            ?: ratios?.eps
            ?: metricsMap["EPS"]?.getValueAsDouble()

        val divYield = valuation?.dividendYieldPct
            ?: ratios?.dividendYieldPct
            ?: metricsMap["DIVIDEND YIELD"]?.getValueAsDouble()

        val netMargin = profitability?.netProfitMarginPct
            ?: ratios?.netProfitMarginPct
            ?: extras?.netProfitMarginPct
            ?: metricsMap["NET PROFIT MARGIN"]?.getValueAsDouble()

        val de = extras?.debtToEquity
            ?: ratios?.debtToEquity
            ?: metricsMap["DEBT-TO-EQUITY"]?.getValueAsDouble()
            ?: metricsMap["DEBT TO EQUITY"]?.getValueAsDouble()

        val currentRatio = extras?.currentRatio
            ?: ratios?.currentRatio
            ?: metricsMap["CURRENT RATIO"]?.getValueAsDouble()

        val quickRatio = extras?.quickRatio
            ?: ratios?.quickRatio
            ?: metricsMap["QUICK RATIO"]?.getValueAsDouble()

        val roe = profitability?.roePct
            ?: extras?.roePct
            ?: metricsMap["ROE"]?.getValueAsDouble()

        val roa = profitability?.roaPct
            ?: extras?.roaPct
            ?: metricsMap["ROA"]?.getValueAsDouble()

        val interestCov = extras?.interestCoverage
            ?: ratios?.interestCoverageRatio
            ?: ratios?.interestCoverage
            ?: metricsMap["INTEREST COVERAGE"]?.getValueAsDouble()

        val pb = valuation?.priceToBook
            ?: extras?.priceToBook
            ?: ratios?.priceToBook
            ?: metricsMap["PRICE TO BOOK"]?.getValueAsDouble()
            ?: metricsMap["P/B RATIO"]?.getValueAsDouble()

        val formattedMarketCap = when {
            shareStructure?.marketCapPkrM != null && shareStructure.marketCapPkrM > 0 -> {
                String.format(Locale.US, "%.1fM", shareStructure.marketCapPkrM)
            }
            shareStructure?.marketCapPkr != null && shareStructure.marketCapPkr > 0 -> {
                String.format(Locale.US, "%.1fB", shareStructure.marketCapPkr / 1_000_000_000.0)
            }
            equity?.marketCapPkrM != null && equity.marketCapPkrM > 0 -> {
                String.format(Locale.US, "%.1fM", equity.marketCapPkrM)
            }
            metricsMap["MARKET CAP (PKR M)"]?.getValueAsDouble() != null -> {
                String.format(Locale.US, "%.1fM", metricsMap["MARKET CAP (PKR M)"]!!.getValueAsDouble()!!)
            }
            else -> null
        }

        val evEbitda = valuation?.evToEbitda
            ?: metricsMap["EV/EBITDA"]?.getValueAsDouble()
            ?: metricsMap["EV EBITDA"]?.getValueAsDouble()

        val fwdPe = metricsMap["FORWARD P/E"]?.getValueAsDouble()
            ?: metricsMap["FORWARD PE"]?.getValueAsDouble()

        val financialUnit = dto.financials?.unit?.takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty()
        val revVal = profitability?.revenue?.let { String.format(Locale.US, "%.2f%s", it, financialUnit) }
            ?: dto.financials?.annual?.firstOrNull()?.let { item ->
                (item.revenue ?: item.sales)?.let { String.format(Locale.US, "%.2f%s", it, financialUnit) }
            }
            ?: metricsMap["REVENUE"]?.getValueAsString()
            ?: metricsMap["REVENUE TTM"]?.getValueAsString()
            ?: metricsMap["SALES"]?.getValueAsString()

        val netIncVal = profitability?.profitAfterTax?.let { String.format(Locale.US, "%.2f%s", it, financialUnit) }
            ?: dto.financials?.annual?.firstOrNull()?.let { item ->
                (item.profitAfterTax ?: item.netProfit)?.let { String.format(Locale.US, "%.2f%s", it, financialUnit) }
            }
            ?: metricsMap["NET INCOME"]?.getValueAsString()
            ?: metricsMap["NET INCOME TTM"]?.getValueAsString()

        val fcfVal = metricsMap["FREE CASH FLOW"]?.getValueAsString()
            ?: metricsMap["FCF"]?.getValueAsString()
            ?: dto.cashFlow?.annual?.firstOrNull()?.freeCashFlow?.let {
                String.format(Locale.US, "%.2f%s", it, financialUnit)
            }

        return FundamentalMetrics(
            peRatio = pe,
            sectorPeAvg = null,
            forwardPe = fwdPe,
            pbRatio = pb,
            evEbitda = evEbitda,
            pegRatio = peg,
            eps = epsVal,
            roe = roe,
            roa = roa,
            dividendYield = divYield,
            netProfitMargin = netMargin,
            debtToEquity = de,
            currentRatio = currentRatio,
            quickRatio = quickRatio,
            interestCoverage = interestCov,
            revenueTTM = revVal,
            revenueGrowthYoY = growth?.revenueGrowthYoyPct
                ?: ratios?.epsGrowthPct
                ?: extras?.epsGrowthPct,
            netIncomeTTM = netIncVal,
            netIncomeGrowthYoY = growth?.profitGrowthYoyPct,
            freeCashFlowTTM = fcfVal
        )
    }

    private fun parseSignal(signal: String?): TechnicalSignal {
        return when (signal?.uppercase()) {
            "BUY" -> TechnicalSignal.BUY
            "STRONG_BUY", "STRONG BUY" -> TechnicalSignal.STRONG_BUY
            "SELL" -> TechnicalSignal.SELL
            "STRONG_SELL", "STRONG SELL" -> TechnicalSignal.STRONG_SELL
            else -> TechnicalSignal.NEUTRAL
        }
    }
}
