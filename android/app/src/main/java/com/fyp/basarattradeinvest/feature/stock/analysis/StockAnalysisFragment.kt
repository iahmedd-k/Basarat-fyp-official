package com.fyp.basarattradeinvest.feature.stock.analysis

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentStockAnalysisBinding
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.ForecastDirection
import com.fyp.basarattradeinvest.domain.model.stock.ForecastHistory
import com.fyp.basarattradeinvest.domain.model.stock.StockAnalysis
import com.fyp.basarattradeinvest.domain.model.stock.StockForecast
import com.fyp.basarattradeinvest.domain.model.stock.TechnicalSignal
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistory
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsItem
import com.fyp.basarattradeinvest.domain.model.sentiment.StockSentiment
import com.fyp.basarattradeinvest.feature.sentiment.adapter.SentimentNewsAdapter
import kotlinx.coroutines.launch
import java.util.Locale

class StockAnalysisFragment : Fragment() {

    private var _binding: FragmentStockAnalysisBinding? = null
    private val binding get() = _binding!!

    private val viewModel: StockAnalysisViewModel by activityViewModels()
    private val sentimentNewsAdapter by lazy { SentimentNewsAdapter() }
    private var lastBoundSuccess: StockAnalysisUiState.Success? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentStockAnalysisBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val symbol = arguments?.getString("symbol") ?: "LUCK"

        binding.tvStockSymbol.text = symbol
        binding.tvCompanyName.text = ""
        binding.tvCurrentPrice.text = "--"
        binding.tvPriceChange.visibility = View.GONE

        setupRecyclerViews()
        setupClickListeners()
        observeUiState()

        viewModel.ensureLoaded(symbol)
    }

    private fun setupRecyclerViews() {
        binding.rvSentimentNews.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = sentimentNewsAdapter
            isNestedScrollingEnabled = false
        }
    }

    private fun setupClickListeners() {
        binding.ivBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnAnalysisRetry.setOnClickListener {
            viewModel.retry()
        }

        // Analysis navigation tabs (in-place tab row)
        binding.btnTabTechnical.setOnClickListener {
            viewModel.selectTab(AnalysisTab.TECHNICAL)
        }

        binding.btnTabFundamentals.setOnClickListener {
            viewModel.selectTab(AnalysisTab.FUNDAMENTALS)
        }

        binding.btnTabForecast.setOnClickListener {
            viewModel.selectTab(AnalysisTab.FORECAST)
        }

        binding.btnTabSentiment.setOnClickListener {
            viewModel.selectTab(AnalysisTab.SENTIMENT)
        }

        // Price History Range pills
        binding.btnRange1d.setOnClickListener { viewModel.selectPriceRange("1D") }
        binding.btnRange1w.setOnClickListener { viewModel.selectPriceRange("1W") }
        binding.btnRange1m.setOnClickListener { viewModel.selectPriceRange("1M") }
        binding.btnRange1y.setOnClickListener { viewModel.selectPriceRange("1Y") }

        binding.btnChartRetry.setOnClickListener {
            viewModel.retryPriceHistory()
        }

        // Forecast Horizon selection pills
        binding.btnHorizon1d.setOnClickListener { viewModel.selectHorizon("1D") }
        binding.btnHorizon1w.setOnClickListener { viewModel.selectHorizon("1W") }
        binding.btnHorizon2w.setOnClickListener { viewModel.selectHorizon("2W") }
        binding.btnHorizon1m.setOnClickListener { viewModel.selectHorizon("1M") }

        // Retry buttons
        binding.btnForecastRetry.setOnClickListener { viewModel.retryForecast() }
        binding.btnForecastHistoryRetry.setOnClickListener { viewModel.retryHistory() }
        binding.btnStockSentimentRetry.setOnClickListener { viewModel.retrySentiment() }
        binding.btnSentimentHistoryRetry.setOnClickListener { viewModel.retrySentiment() }
        binding.btnSentimentNewsRetry.setOnClickListener { viewModel.retrySentiment() }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is StockAnalysisUiState.Loading -> {
                            lastBoundSuccess = null
                            binding.layoutAnalysisLoading.visibility = View.VISIBLE
                            binding.layoutAnalysisError.visibility = View.GONE
                            binding.layoutTechnicalContent.visibility = View.GONE
                            binding.layoutFundamentalsContent.visibility = View.GONE
                            binding.layoutForecastContent.visibility = View.GONE
                            binding.layoutSentimentContent.visibility = View.GONE
                            binding.layoutAnalysisLoading.bringToFront()
                        }
                        is StockAnalysisUiState.Error -> {
                            lastBoundSuccess = null
                            binding.layoutAnalysisLoading.visibility = View.GONE
                            binding.layoutAnalysisError.visibility = View.VISIBLE
                            binding.tvAnalysisErrorMsg.text = state.message
                            binding.layoutTechnicalContent.visibility = View.GONE
                            binding.layoutFundamentalsContent.visibility = View.GONE
                            binding.layoutForecastContent.visibility = View.GONE
                            binding.layoutSentimentContent.visibility = View.GONE
                        }
                        is StockAnalysisUiState.Empty -> {
                            lastBoundSuccess = null
                            binding.layoutAnalysisLoading.visibility = View.GONE
                            binding.layoutAnalysisError.visibility = View.VISIBLE
                            binding.tvAnalysisErrorMsg.text = "No stock analysis data available."
                            binding.layoutTechnicalContent.visibility = View.GONE
                            binding.layoutFundamentalsContent.visibility = View.GONE
                            binding.layoutForecastContent.visibility = View.GONE
                            binding.layoutSentimentContent.visibility = View.GONE
                        }
                        is StockAnalysisUiState.Success -> {
                            binding.layoutAnalysisLoading.visibility = View.GONE
                            binding.layoutAnalysisError.visibility = View.GONE

                            // Each section arrives as its own state emission, so rebind only the
                            // sections whose input actually changed. Rebuilding a chart restarts
                            // its entry animation and is the visible cost here.
                            val previous = lastBoundSuccess
                            if (previous == null || previous.analysis != state.analysis) {
                                renderHeader(state.analysis)
                                renderTechnicalSummary(state.analysis)
                                renderFundamentals(state.analysis)
                            }
                            if (previous == null || previous.selectedTab != state.selectedTab) {
                                renderTab(state.selectedTab)
                            }
                            if (previous == null ||
                                previous.priceHistoryState != state.priceHistoryState ||
                                previous.selectedPriceRange != state.selectedPriceRange
                            ) {
                                renderPriceHistorySection(state.priceHistoryState, state.selectedPriceRange)
                            }
                            if (previous == null ||
                                previous.forecastState != state.forecastState ||
                                previous.selectedHorizon != state.selectedHorizon
                            ) {
                                renderForecastSection(state.forecastState, state.selectedHorizon)
                            }
                            if (previous == null ||
                                previous.historyState != state.historyState ||
                                previous.selectedHorizon != state.selectedHorizon
                            ) {
                                renderForecastHistory(state.historyState, state.selectedHorizon)
                            }
                            if (previous == null || previous.sentimentState != state.sentimentState) {
                                renderStockSentiment(state.sentimentState)
                            }
                            if (previous == null || previous.sentimentHistoryState != state.sentimentHistoryState) {
                                renderSentimentHistory(state.sentimentHistoryState)
                            }
                            if (previous == null || previous.sentimentNewsState != state.sentimentNewsState) {
                                renderSentimentNews(state.sentimentNewsState)
                            }

                            lastBoundSuccess = state
                        }
                    }
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  HEADER & TAB NAVIGATION
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderHeader(analysis: StockAnalysis) {
        binding.tvStockSymbol.text = analysis.symbol
        binding.tvCompanyName.text = analysis.companyName

        if (analysis.price > 0.0) {
            binding.tvCurrentPrice.text = String.format(Locale.US, "PKR %.2f", analysis.price)

            val sign = if (analysis.changeAmount >= 0) "+" else ""
            binding.tvPriceChange.text = String.format(
                Locale.US,
                "%s%.2f (%s%.2f%%)",
                sign,
                analysis.changeAmount,
                sign,
                analysis.changePercent
            )
            binding.tvPriceChange.visibility = View.VISIBLE

            val isPositive = analysis.changeAmount >= 0
            binding.tvPriceChange.setTextColor(
                ContextCompat.getColor(
                    requireContext(),
                    if (isPositive) R.color.color_positive else R.color.color_negative
                )
            )
            binding.tvPriceChange.setBackgroundResource(
                if (isPositive) R.drawable.bg_badge_positive else R.drawable.bg_badge_negative
            )
        } else {
            binding.tvCurrentPrice.text = "Price unavailable"
            binding.tvPriceChange.visibility = View.GONE
        }
    }

    private fun renderTab(tab: AnalysisTab) {
        val primaryText = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val secondaryText = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        // Reset all tabs
        binding.tvTabTechnicalText.setTextColor(secondaryText)
        binding.indicatorTabTechnical.visibility = View.INVISIBLE

        binding.tvTabFundamentalsText.setTextColor(secondaryText)
        binding.indicatorTabFundamentals.visibility = View.INVISIBLE

        binding.tvTabForecastText.setTextColor(secondaryText)
        binding.indicatorTabForecast.visibility = View.INVISIBLE

        binding.tvTabSentimentText.setTextColor(secondaryText)
        binding.indicatorTabSentiment.visibility = View.INVISIBLE

        when (tab) {
            AnalysisTab.TECHNICAL -> {
                binding.tvTabTechnicalText.setTextColor(primaryText)
                binding.indicatorTabTechnical.visibility = View.VISIBLE

                binding.layoutTechnicalContent.visibility = View.VISIBLE
                binding.layoutFundamentalsContent.visibility = View.GONE
                binding.layoutForecastContent.visibility = View.GONE
                binding.layoutSentimentContent.visibility = View.GONE
            }
            AnalysisTab.FUNDAMENTALS -> {
                binding.tvTabFundamentalsText.setTextColor(primaryText)
                binding.indicatorTabFundamentals.visibility = View.VISIBLE

                binding.layoutTechnicalContent.visibility = View.GONE
                binding.layoutFundamentalsContent.visibility = View.VISIBLE
                binding.layoutForecastContent.visibility = View.GONE
                binding.layoutSentimentContent.visibility = View.GONE
            }
            AnalysisTab.FORECAST -> {
                binding.tvTabForecastText.setTextColor(primaryText)
                binding.indicatorTabForecast.visibility = View.VISIBLE

                binding.layoutTechnicalContent.visibility = View.GONE
                binding.layoutFundamentalsContent.visibility = View.GONE
                binding.layoutForecastContent.visibility = View.VISIBLE
                binding.layoutSentimentContent.visibility = View.GONE
            }
            AnalysisTab.SENTIMENT -> {
                binding.tvTabSentimentText.setTextColor(primaryText)
                binding.indicatorTabSentiment.visibility = View.VISIBLE

                binding.layoutTechnicalContent.visibility = View.GONE
                binding.layoutFundamentalsContent.visibility = View.GONE
                binding.layoutForecastContent.visibility = View.GONE
                binding.layoutSentimentContent.visibility = View.VISIBLE
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  TAB 1: TECHNICAL ANALYSIS
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderTechnicalSummary(analysis: StockAnalysis) {
        val tech = analysis.technical
        binding.tvCountBuy.text = tech.summary.buyCount.toString()
        binding.tvCountNeutral.text = tech.summary.neutralCount.toString()
        binding.tvCountSell.text = tech.summary.sellCount.toString()
        binding.tvProminentSignal.text = tech.summary.overallSignal.label
        applyBadgeStyle(binding.tvProminentSignal, tech.summary.overallSignal)

        // Dynamically adjust meter weights to match backend signals breakdown
        val total = (tech.summary.buyCount + tech.summary.neutralCount + tech.summary.sellCount).toFloat()
        if (total > 0f) {
            (binding.barBuy.layoutParams as LinearLayout.LayoutParams).weight = tech.summary.buyCount.toFloat()
            (binding.barNeutral.layoutParams as LinearLayout.LayoutParams).weight = tech.summary.neutralCount.toFloat()
            (binding.barSell.layoutParams as LinearLayout.LayoutParams).weight = tech.summary.sellCount.toFloat()
            binding.layoutMeterBar.requestLayout()
        }

        // Oscillators mapping (real backend data only)
        tech.oscillators.forEach { indicator ->
            when {
                indicator.name.contains("RSI", ignoreCase = true) -> {
                    binding.tvValRsi.text = indicator.value
                    binding.tvBadgeRsi.text = indicator.signal.label
                    applyBadgeStyle(binding.tvBadgeRsi, indicator.signal)
                }
                indicator.name.contains("MACD", ignoreCase = true) -> {
                    binding.tvValMacd.text = indicator.value
                    binding.tvBadgeMacd.text = indicator.signal.label
                    applyBadgeStyle(binding.tvBadgeMacd, indicator.signal)
                }
                indicator.name.contains("ADX", ignoreCase = true) -> {
                    binding.tvValAdx.text = indicator.value
                    binding.tvBadgeAdx.text = indicator.signal.label
                    applyBadgeStyle(binding.tvBadgeAdx, indicator.signal)
                }
                indicator.name.contains("Stochastic", ignoreCase = true) -> {
                    binding.rowStoch.visibility = View.VISIBLE
                    binding.tvValStoch.text = indicator.value
                    binding.tvBadgeStoch.text = indicator.signal.label
                    applyBadgeStyle(binding.tvBadgeStoch, indicator.signal)
                }
                indicator.name.contains("Bollinger", ignoreCase = true) -> {
                    binding.tvValBb.text = indicator.value
                    binding.tvBadgeBb.text = indicator.signal.label
                    applyBadgeStyle(binding.tvBadgeBb, indicator.signal)
                }
            }
        }

        // Moving averages mapping
        tech.movingAverages.forEach { ma ->
            if (ma.name.contains("SMA", ignoreCase = true)) {
                binding.tvValSma.text = ma.value
                binding.tvBadgeSma.text = ma.signal.label
                applyBadgeStyle(binding.tvBadgeSma, ma.signal)
            }
        }
    }

    private fun renderPriceHistorySection(state: PriceHistorySectionState, selectedRange: String) {
        val activeBg = ContextCompat.getDrawable(requireContext(), R.drawable.bg_segmented_tab_active)
        val primaryText = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val secondaryText = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        binding.btnRange1d.background = if (selectedRange == "1D") activeBg else null
        binding.btnRange1d.setTextColor(if (selectedRange == "1D") primaryText else secondaryText)

        binding.btnRange1w.background = if (selectedRange == "1W") activeBg else null
        binding.btnRange1w.setTextColor(if (selectedRange == "1W") primaryText else secondaryText)

        binding.btnRange1m.background = if (selectedRange == "1M") activeBg else null
        binding.btnRange1m.setTextColor(if (selectedRange == "1M") primaryText else secondaryText)

        binding.btnRange1y.background = if (selectedRange == "1Y") activeBg else null
        binding.btnRange1y.setTextColor(if (selectedRange == "1Y") primaryText else secondaryText)

        when (state) {
            is PriceHistorySectionState.Loading -> {
                binding.chartPriceProgress.visibility = View.VISIBLE
                binding.layoutChartError.visibility = View.GONE
                binding.tvChartEmpty.visibility = View.GONE
                binding.chartPriceHistory.visibility = View.GONE
            }
            is PriceHistorySectionState.Error -> {
                binding.chartPriceProgress.visibility = View.GONE
                binding.layoutChartError.visibility = View.VISIBLE
                binding.tvChartEmpty.visibility = View.GONE
                binding.chartPriceHistory.visibility = View.GONE
            }
            is PriceHistorySectionState.Empty -> {
                binding.chartPriceProgress.visibility = View.GONE
                binding.layoutChartError.visibility = View.GONE
                binding.tvChartEmpty.visibility = View.VISIBLE
                binding.chartPriceHistory.visibility = View.GONE
            }
            is PriceHistorySectionState.Success -> {
                binding.chartPriceProgress.visibility = View.GONE
                binding.layoutChartError.visibility = View.GONE
                binding.tvChartEmpty.visibility = View.GONE
                binding.chartPriceHistory.visibility = View.VISIBLE
                renderPriceChart(state.candles)
            }
        }
    }

    private fun renderPriceChart(candles: List<CandleEntry>) {
        val chart = binding.chartPriceHistory
        if (candles.isEmpty()) {
            chart.visibility = View.GONE
            binding.tvChartEmpty.visibility = View.VISIBLE
            return
        }

        val ctx = requireContext()
        val isUp = (candles.lastOrNull()?.close ?: 0f) >= (candles.firstOrNull()?.open ?: 0f)
        val lineColor = ContextCompat.getColor(
            ctx,
            if (isUp) R.color.color_positive else R.color.color_negative
        )
        val chartTextColor = ContextCompat.getColor(ctx, R.color.color_text_secondary)
        val chartGridColor = ContextCompat.getColor(ctx, R.color.color_divider)

        val entries = candles.mapIndexed { index, candle ->
            Entry(index.toFloat(), candle.close)
        }

        val dataSet = LineDataSet(entries, "Price").apply {
            color = lineColor
            lineWidth = 2f
            setDrawCircles(false)
            setDrawValues(false)
            mode = LineDataSet.Mode.CUBIC_BEZIER
            setDrawFilled(true)
            fillAlpha = 35
            fillColor = lineColor
        }

        chart.apply {
            data = LineData(dataSet)
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(true)
            isDragEnabled = true
            setScaleEnabled(false)
            setPinchZoom(false)

            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                textColor = chartTextColor
                setDrawGridLines(false)
                setDrawAxisLine(true)
                axisLineColor = chartGridColor
                textSize = 9f
            }

            axisLeft.apply {
                textColor = chartTextColor
                gridColor = chartGridColor
                setDrawAxisLine(false)
                textSize = 9f
            }

            axisRight.isEnabled = false
            animateX(400)
            invalidate()
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  TAB 2: FUNDAMENTALS
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderFundamentals(analysis: StockAnalysis) {
        val fund = analysis.fundamentals

        binding.tvValPe.text = formatMultiple(fund.peRatio)
        binding.tvValForwardPe.text = formatMultiple(fund.forwardPe)
        binding.tvValPb.text = formatMultiple(fund.pbRatio)
        binding.tvValPeg.text = formatRatio(fund.pegRatio)
        binding.tvValEvEbitda.text = formatMultiple(fund.evEbitda)

        binding.tvValEps.text = formatCurrency(fund.eps)
        binding.tvValRoe.text = formatPercent(fund.roe)
        binding.tvValRoa.text = formatPercent(fund.roa)
        binding.tvValNetMargin.text = formatPercent(fund.netProfitMargin)
        binding.tvValDivYield.text = formatPercent(fund.dividendYield)

        binding.tvValDe.text = formatRatio(fund.debtToEquity)
        binding.tvValCurrentRatio.text = formatMultiple(fund.currentRatio)
        binding.tvValQuickRatio.text = formatMultiple(fund.quickRatio)
        binding.tvValInterestCoverage.text = formatMultiple(fund.interestCoverage)

        binding.tvValRevenue.text = fund.revenueTTM ?: "N/A"
        binding.tvValNetIncome.text = fund.netIncomeTTM ?: "N/A"
        binding.tvValFcf.text = fund.freeCashFlowTTM ?: "N/A"
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  TAB 3: FORECAST
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderForecastSection(state: ForecastSectionState, selectedHorizon: String) {
        val activeBg = ContextCompat.getDrawable(requireContext(), R.drawable.bg_segmented_tab_active)
        val primaryText = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val secondaryText = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        binding.btnHorizon1d.background = if (selectedHorizon == "1D") activeBg else null
        binding.btnHorizon1d.setTextColor(if (selectedHorizon == "1D") primaryText else secondaryText)

        binding.btnHorizon1w.background = if (selectedHorizon == "1W") activeBg else null
        binding.btnHorizon1w.setTextColor(if (selectedHorizon == "1W") primaryText else secondaryText)

        binding.btnHorizon2w.background = if (selectedHorizon == "2W") activeBg else null
        binding.btnHorizon2w.setTextColor(if (selectedHorizon == "2W") primaryText else secondaryText)

        binding.btnHorizon1m.background = if (selectedHorizon == "1M") activeBg else null
        binding.btnHorizon1m.setTextColor(if (selectedHorizon == "1M") primaryText else secondaryText)

        when (state) {
            is ForecastSectionState.Loading -> {
                binding.layoutForecastLoading.visibility = View.VISIBLE
                binding.layoutForecastError.visibility = View.GONE
                binding.layoutForecastSuccess.visibility = View.GONE
            }
            is ForecastSectionState.Error -> {
                binding.layoutForecastLoading.visibility = View.GONE
                binding.layoutForecastError.visibility = View.VISIBLE
                binding.layoutForecastSuccess.visibility = View.GONE
                binding.tvForecastErrorMsg.text = state.message
            }
            is ForecastSectionState.Empty -> {
                binding.layoutForecastLoading.visibility = View.GONE
                binding.layoutForecastError.visibility = View.VISIBLE
                binding.layoutForecastSuccess.visibility = View.GONE
                binding.tvForecastErrorMsg.text = "No forecast data available for this horizon."
            }
            is ForecastSectionState.Success -> {
                binding.layoutForecastLoading.visibility = View.GONE
                binding.layoutForecastError.visibility = View.GONE
                binding.layoutForecastSuccess.visibility = View.VISIBLE
                bindForecastData(state.forecast)
            }
        }
    }

    private fun bindForecastData(forecast: StockForecast) {
        val context = requireContext()

        // Dates
        binding.tvForecastDates.apply {
            text = forecast.targetDate.takeIf { it.isNotBlank() }?.let { "Target: $it" }.orEmpty()
            visibility = if (text.isNotBlank()) View.VISIBLE else View.GONE
        }

        val displayDirection = when (forecast.direction) {
            ForecastDirection.SIDEWAYS -> "Neutral"
            else -> forecast.direction.label
        }

        // Direction Badge
        binding.tvForecastDirectionBadge.text = displayDirection.uppercase()
        when (forecast.direction) {
            ForecastDirection.BULLISH -> {
                binding.tvForecastDirectionBadge.setBackgroundResource(R.drawable.bg_badge_positive)
                binding.tvForecastDirectionBadge.setTextColor(ContextCompat.getColor(context, R.color.color_positive))
            }
            ForecastDirection.BEARISH -> {
                binding.tvForecastDirectionBadge.setBackgroundResource(R.drawable.bg_badge_negative)
                binding.tvForecastDirectionBadge.setTextColor(ContextCompat.getColor(context, R.color.color_negative))
            }
            ForecastDirection.SIDEWAYS -> {
                binding.tvForecastDirectionBadge.setBackgroundResource(R.drawable.bg_badge_neutral)
                binding.tvForecastDirectionBadge.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
            }
        }

        // Signal Rating
        val signalRating = forecast.signalRating?.takeIf { it.isNotBlank() } ?: "N/A"
        binding.tvForecastSignalRating.text = signalRating.uppercase()
        when {
            signalRating.contains("Buy", ignoreCase = true) -> {
                binding.tvForecastSignalRating.setBackgroundResource(R.drawable.bg_badge_strong_buy)
                binding.tvForecastSignalRating.setTextColor(ContextCompat.getColor(context, R.color.color_basarat_green))
            }
            signalRating.contains("Sell", ignoreCase = true) -> {
                binding.tvForecastSignalRating.setBackgroundResource(R.drawable.bg_badge_negative)
                binding.tvForecastSignalRating.setTextColor(ContextCompat.getColor(context, R.color.color_negative))
            }
            else -> {
                binding.tvForecastSignalRating.setBackgroundResource(R.drawable.bg_badge_neutral)
                binding.tvForecastSignalRating.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
            }
        }

        // Confidence
        val confPct = (forecast.confidence * 100).toInt()
        binding.tvForecastConfidence.text = "Confidence: $confPct%"

        val targetPriceText = forecast.targetPrice?.let { String.format(Locale.US, "PKR %.2f", it) } ?: "N/A"
        val upsideText = forecast.upsidePct?.let {
            if (it >= 0.0) String.format(Locale.US, "%+,.1f%% upside", it)
            else String.format(Locale.US, "%,.1f%% downside", it)
        } ?: "--"

        val summaryDirection = when (forecast.direction) {
            ForecastDirection.BULLISH -> "Bullish"
            ForecastDirection.BEARISH -> "Bearish"
            ForecastDirection.SIDEWAYS -> "Neutral"
        }

        val summaryParts = mutableListOf("Forecast: $summaryDirection")
        forecast.targetPrice?.let { summaryParts += "Target PKR ${String.format(Locale.US, "%.2f", it)}" }
        forecast.upsidePct?.let {
            summaryParts += String.format(Locale.US, "%+.1f%%", it)
        }
        binding.tvForecastSummary.text = summaryParts.joinToString(" · ")
        binding.tvForecastMeta.text = listOfNotNull(
            "${forecast.horizon} outlook",
            forecast.asOfDate.takeIf { it.isNotBlank() }?.let { "As of: $it" },
        ).joinToString(" • ")

        // Prices & Targets
        binding.tvForecastTargetPrice.text = targetPriceText
        binding.tvForecastUpsidePct.text = upsideText

        binding.tvForecastStopLoss.text = forecast.stopLoss?.let { String.format(Locale.US, "PKR %.2f", it) } ?: "N/A"
        binding.tvForecastDownsidePct.text = forecast.downsidePct?.let {
            if (it <= 0.0) String.format(Locale.US, "%,.1f%% risk", it)
            else String.format(Locale.US, "%+,.1f%% stop", it)
        } ?: "--"

        binding.tvForecastRiskReward.text = forecast.riskRewardRatio?.let { String.format(Locale.US, "%.2f", it) } ?: "N/A"
        binding.tvForecastCurrentPrice.text = forecast.currentPrice?.let { String.format(Locale.US, "Ref: PKR %.2f", it) } ?: ""

        bindForecastProbabilities(forecast)
        // Per-model names and scores are implementation details, so keep the internal
        // breakdown out of the investor-facing forecast screen.
        binding.cardModelBreakdown.visibility = View.GONE
        binding.cardMarketContext.visibility = View.GONE
    }

    private fun renderForecastHistory(state: ForecastHistorySectionState, horizon: String) {
        val card = binding.cardForecastHistory
        val summary = binding.tvForecastHistorySummary
        val rows = binding.layoutForecastHistoryRows
        val retry = binding.btnForecastHistoryRetry
        rows.removeAllViews()
        card.visibility = View.VISIBLE
        retry.visibility = View.GONE

        when (state) {
            ForecastHistorySectionState.Loading -> {
                summary.text = "Loading saved forecasts for $horizon…"
            }
            ForecastHistorySectionState.Empty -> {
                summary.text = "No saved forecasts are available for $horizon yet."
            }
            is ForecastHistorySectionState.Error -> {
                summary.text = state.message
                retry.visibility = View.VISIBLE
            }
            is ForecastHistorySectionState.Success -> {
                val history = state.history
                val accuracy = history.accuracy?.let { probabilityPercent(it) }
                    ?.let { String.format(Locale.US, "%.1f%% accuracy", it) }
                summary.text = listOfNotNull(
                    "${history.count} saved forecasts",
                    accuracy
                ).joinToString(" · ")
                history.history.take(5).forEach { record ->
                    val actual = record.actualOutcome
                    val outcome = when {
                        actual == null -> "Pending evaluation"
                        actual.wasCorrect == true -> "Correct · actual ${actual.direction}"
                        actual.wasCorrect == false -> "Incorrect · actual ${actual.direction}"
                        actual.direction != "unknown" -> "Actual ${actual.direction}"
                        else -> "Evaluated"
                    }
                    rows.addView(TextView(requireContext()).apply {
                        text = "${record.predictedAt.ifBlank { "Forecast" }}  ·  ${record.predictedDirection.label}\nTarget ${record.targetDate.ifBlank { "—" }}  ·  $outcome"
                        textSize = 12f
                        setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
                        setPadding(0, dp(8), 0, dp(8))
                    })
                }
            }
        }
    }

    private fun bindForecastProbabilities(forecast: StockForecast) {
        val probabilities = forecast.probabilities
        val bullish = probabilityPercent(probabilities?.bullish)
        val sideways = probabilityPercent(probabilities?.sideways)
        val bearish = probabilityPercent(probabilities?.bearish)
        val hasProbability = listOf(bullish, sideways, bearish).any { it != null }
        binding.cardForecastProbabilities.visibility = if (hasProbability) View.VISIBLE else View.GONE
        if (!hasProbability) return

        binding.tvProbBullishVal.text = bullish?.let { String.format(Locale.US, "Bullish: %.1f%%", it) } ?: "Bullish: N/A"
        binding.tvProbSidewaysVal.text = sideways?.let { String.format(Locale.US, "Sideways: %.1f%%", it) } ?: "Sideways: N/A"
        binding.tvProbBearishVal.text = bearish?.let { String.format(Locale.US, "Bearish: %.1f%%", it) } ?: "Bearish: N/A"

        val values = listOf(bullish, sideways, bearish)
        val total = values.filterNotNull().sum().takeIf { it > 0.0 }
        val bars = listOf(binding.barProbBullish, binding.barProbSideways, binding.barProbBearish)
        bars.forEachIndexed { index, bar ->
            val value = values[index]
            bar.visibility = if (value != null && value > 0.0 && total != null) View.VISIBLE else View.GONE
            (bar.layoutParams as? LinearLayout.LayoutParams)?.let { params ->
                params.weight = if (value != null && total != null) value.toFloat() else 0f
                bar.layoutParams = params
            }
        }
        binding.layoutProbMeter.visibility = if (total != null) View.VISIBLE else View.GONE
    }

    private fun probabilityPercent(value: Double?): Double? = value?.let {
        (if (kotlin.math.abs(it) <= 1.0) it * 100.0 else it).coerceIn(0.0, 100.0)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    // ─────────────────────────────────────────────────────────────────────────
    //  TAB 4: SENTIMENT
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderStockSentiment(state: StockSentimentSectionState) {
        when (state) {
            is StockSentimentSectionState.Loading -> {
                binding.progressStockSentiment.visibility = View.VISIBLE
                binding.layoutStockSentimentError.visibility = View.GONE
                binding.cardStockSentiment.visibility = View.GONE
            }
            is StockSentimentSectionState.Error -> {
                binding.progressStockSentiment.visibility = View.GONE
                binding.layoutStockSentimentError.visibility = View.VISIBLE
                binding.cardStockSentiment.visibility = View.GONE
                binding.tvStockSentimentErrorMsg.text = state.message
            }
            is StockSentimentSectionState.Empty -> {
                binding.progressStockSentiment.visibility = View.GONE
                binding.layoutStockSentimentError.visibility = View.GONE
                binding.cardStockSentiment.visibility = View.GONE
            }
            is StockSentimentSectionState.Success -> {
                binding.progressStockSentiment.visibility = View.GONE
                binding.layoutStockSentimentError.visibility = View.GONE
                binding.cardStockSentiment.visibility = View.VISIBLE
                bindStockSentimentData(state.sentiment)
            }
        }
    }

    private fun bindStockSentimentData(data: StockSentiment) {
        val ctx = requireContext()
        binding.tvSentimentStockLabel.text = data.label.uppercase(Locale.getDefault())

        val scoreText = String.format(Locale.US, "%+.2f", data.score)
        binding.tvSentimentStockScoreValue.text = scoreText
        val scoreColor = when {
            data.score > 0f -> ContextCompat.getColor(ctx, R.color.color_positive)
            data.score < 0f -> ContextCompat.getColor(ctx, R.color.color_negative)
            else -> ContextCompat.getColor(ctx, R.color.color_text_secondary)
        }
        binding.tvSentimentStockScoreValue.setTextColor(scoreColor)

        // Map score -1.0..+1.0 onto 0..100% of track width
        val pct = ((data.score + 1f) / 2f).coerceIn(0f, 1f)
        binding.viewSentimentScoreFill.post {
            val totalWidth = (binding.viewSentimentScoreFill.parent as? View)?.width ?: 0
            if (totalWidth > 0) {
                val fillWidth = (pct * totalWidth).toInt()
                val params = binding.viewSentimentScoreFill.layoutParams
                params.width = fillWidth
                binding.viewSentimentScoreFill.layoutParams = params

                val barColor = when {
                    data.score > 0.05f -> ContextCompat.getColor(ctx, R.color.color_positive)
                    data.score < -0.05f -> ContextCompat.getColor(ctx, R.color.color_negative)
                    else -> ContextCompat.getColor(ctx, R.color.color_neutral)
                }
                binding.viewSentimentScoreFill.setBackgroundColor(barColor)
            }
        }

        binding.tvSentimentArticleCount.text = "Articles Scored: ${data.articleCount}"

        val trendIcon = when (data.trend.lowercase(Locale.getDefault())) {
            "improving" -> "↑"
            "declining" -> "↓"
            else -> "→"
        }
        binding.tvSentimentTrend.text = "Trend: ${data.trend.replaceFirstChar { it.uppercase() }} $trendIcon"

        if (data.newsSourceCount > 0 || data.communitySourceCount > 0) {
            binding.tvSentimentSourcesCount.visibility = View.VISIBLE
            binding.tvSentimentSourcesCount.text = "${data.newsSourceCount} news items • ${data.communitySourceCount} community signals"
        } else {
            binding.tvSentimentSourcesCount.visibility = View.GONE
        }
    }

    private fun renderSentimentHistory(state: SentimentHistorySectionState) {
        when (state) {
            is SentimentHistorySectionState.Loading -> {
                binding.progressSentimentHistory.visibility = View.VISIBLE
                binding.layoutSentimentHistoryError.visibility = View.GONE
                binding.tvSentimentHistoryEmpty.visibility = View.GONE
                binding.chartSentimentHistory.visibility = View.GONE
            }
            is SentimentHistorySectionState.Error -> {
                binding.progressSentimentHistory.visibility = View.GONE
                binding.layoutSentimentHistoryError.visibility = View.VISIBLE
                binding.tvSentimentHistoryEmpty.visibility = View.GONE
                binding.chartSentimentHistory.visibility = View.GONE
            }
            is SentimentHistorySectionState.Empty -> {
                binding.progressSentimentHistory.visibility = View.GONE
                binding.layoutSentimentHistoryError.visibility = View.GONE
                binding.tvSentimentHistoryEmpty.visibility = View.VISIBLE
                binding.chartSentimentHistory.visibility = View.GONE
            }
            is SentimentHistorySectionState.Success -> {
                binding.progressSentimentHistory.visibility = View.GONE
                binding.layoutSentimentHistoryError.visibility = View.GONE
                binding.tvSentimentHistoryEmpty.visibility = View.GONE
                binding.chartSentimentHistory.visibility = View.VISIBLE
                renderSentimentChart(state.history)
            }
        }
    }

    private fun renderSentimentChart(history: SentimentHistory) {
        val chart = binding.chartSentimentHistory
        val ctx = requireContext()

        val chartTextColor = ContextCompat.getColor(ctx, R.color.color_text_secondary)
        val chartGridColor = ContextCompat.getColor(ctx, R.color.color_divider)
        val greenColor = ContextCompat.getColor(ctx, R.color.color_basarat_green)

        val entries = history.data.mapIndexed { index, point ->
            Entry(index.toFloat(), point.score)
        }

        if (entries.isEmpty()) {
            chart.visibility = View.GONE
            binding.tvSentimentHistoryEmpty.visibility = View.VISIBLE
            return
        }

        val dataSet = LineDataSet(entries, "Sentiment Score").apply {
            color = greenColor
            setCircleColor(greenColor)
            circleRadius = 2.5f
            setDrawCircleHole(false)
            setDrawValues(false)
            lineWidth = 2f
            mode = LineDataSet.Mode.CUBIC_BEZIER
            setDrawFilled(true)
            fillAlpha = 30
            fillColor = greenColor
        }

        chart.apply {
            data = LineData(dataSet)
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(true)
            setScaleEnabled(false)

            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                textColor = chartTextColor
                gridColor = chartGridColor
                setDrawGridLines(false)
                textSize = 9f
            }

            axisLeft.apply {
                textColor = chartTextColor
                gridColor = chartGridColor
                axisMinimum = -1f
                axisMaximum = 1f
                textSize = 9f
            }

            axisRight.isEnabled = false
            animateX(350)
            invalidate()
        }
    }

    private fun renderSentimentNews(state: SentimentNewsSectionState) {
        when (state) {
            is SentimentNewsSectionState.Loading -> {
                binding.progressSentimentNews.visibility = View.VISIBLE
                binding.layoutSentimentNewsError.visibility = View.GONE
                binding.tvSentimentNewsEmpty.visibility = View.GONE
                binding.rvSentimentNews.visibility = View.GONE
            }
            is SentimentNewsSectionState.Error -> {
                binding.progressSentimentNews.visibility = View.GONE
                binding.layoutSentimentNewsError.visibility = View.VISIBLE
                binding.tvSentimentNewsEmpty.visibility = View.GONE
                binding.rvSentimentNews.visibility = View.GONE
                binding.tvSentimentNewsErrorMsg.text = state.message
            }
            is SentimentNewsSectionState.Empty -> {
                binding.progressSentimentNews.visibility = View.GONE
                binding.layoutSentimentNewsError.visibility = View.GONE
                binding.tvSentimentNewsEmpty.visibility = View.VISIBLE
                binding.rvSentimentNews.visibility = View.GONE
            }
            is SentimentNewsSectionState.Success -> {
                binding.progressSentimentNews.visibility = View.GONE
                binding.layoutSentimentNewsError.visibility = View.GONE
                binding.tvSentimentNewsEmpty.visibility = View.GONE
                binding.rvSentimentNews.visibility = View.VISIBLE
                sentimentNewsAdapter.submitList(state.news)
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  FORMATTING & BADGE HELPERS
    // ─────────────────────────────────────────────────────────────────────────

    private fun formatMultiple(value: Double?): String =
        value?.let { String.format(Locale.US, "%.2fx", it) } ?: "N/A"

    private fun formatRatio(value: Double?): String =
        value?.let { String.format(Locale.US, "%.2f", it) } ?: "N/A"

    private fun formatPercent(value: Double?): String =
        value?.let { String.format(Locale.US, "%.2f%%", it) } ?: "N/A"

    private fun formatCurrency(value: Double?): String =
        value?.let { String.format(Locale.US, "PKR %.2f", it) } ?: "N/A"

    private fun applyBadgeStyle(textView: TextView, signal: TechnicalSignal) {
        val ctx = requireContext()
        when (signal) {
            TechnicalSignal.STRONG_BUY -> {
                textView.setBackgroundResource(R.drawable.bg_badge_strong_buy)
                textView.setTextColor(ContextCompat.getColor(ctx, R.color.color_basarat_green))
            }
            TechnicalSignal.BUY -> {
                textView.setBackgroundResource(R.drawable.bg_badge_positive)
                textView.setTextColor(ContextCompat.getColor(ctx, R.color.color_positive))
            }
            TechnicalSignal.NEUTRAL -> {
                textView.setBackgroundResource(R.drawable.bg_badge_neutral)
                textView.setTextColor(ContextCompat.getColor(ctx, R.color.color_text_secondary))
            }
            TechnicalSignal.SELL, TechnicalSignal.STRONG_SELL -> {
                textView.setBackgroundResource(R.drawable.bg_badge_negative)
                textView.setTextColor(ContextCompat.getColor(ctx, R.color.color_negative))
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        lastBoundSuccess = null
        _binding = null
    }
}
