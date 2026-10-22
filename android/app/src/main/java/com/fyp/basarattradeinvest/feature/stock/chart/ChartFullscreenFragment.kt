package com.fyp.basarattradeinvest.feature.stock.chart

import android.graphics.Color
import android.graphics.Paint
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentChartFullscreenBinding
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.stock.StockDetail
import com.github.mikephil.charting.charts.BarChart
import com.github.mikephil.charting.charts.CandleStickChart
import com.github.mikephil.charting.components.LimitLine
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.BarData
import com.github.mikephil.charting.data.BarDataSet
import com.github.mikephil.charting.data.BarEntry
import com.github.mikephil.charting.data.CandleData
import com.github.mikephil.charting.data.CandleDataSet
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.highlight.Highlight
import com.github.mikephil.charting.listener.OnChartValueSelectedListener
import kotlinx.coroutines.launch
import java.util.Locale

class ChartFullscreenFragment : Fragment() {

    private var _binding: FragmentChartFullscreenBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ChartFullscreenViewModel by activityViewModels()

    private var candleChart: CandleStickChart? = null
    private var volumeChart: BarChart? = null

    private var symbol: String = "LUCK"
    private var cachedCandles: List<CandleEntry> = emptyList()
    private var lastBoundDetail: StockDetail? = null
    private var lastBoundCandles: List<CandleEntry>? = null
    private var lastBoundOhlcCandle: CandleEntry? = null
    private val ohlcDateFormat = java.text.SimpleDateFormat("yyyy-MM-dd", Locale.US)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        arguments?.getString("symbol")?.let {
            symbol = it
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentChartFullscreenBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupCharts()
        setupListeners()
        observeUiState()

        viewModel.ensureLoaded(symbol)
    }

    private fun setupCharts() {
        val context = requireContext()
        val textColor = ContextCompat.getColor(context, R.color.color_text_secondary)
        val bgColor = ContextCompat.getColor(context, R.color.color_background)
        val gridColor = Color.parseColor("#14667085")

        // 1. Candlestick Chart (Main Pane)
        candleChart = CandleStickChart(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(bgColor)
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(true)
            isDragEnabled = true
            setScaleEnabled(true)
            setPinchZoom(true)
            setDrawGridBackground(false)
            isHighlightPerDragEnabled = true

            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                setDrawGridLines(true)
                this.gridColor = gridColor
                this.textColor = textColor
                textSize = 9f
                setDrawLabels(true)
                setAvoidFirstLastClipping(true)
            }

            axisLeft.isEnabled = false

            axisRight.apply {
                isEnabled = true
                setDrawGridLines(true)
                this.gridColor = gridColor
                this.textColor = textColor
                textSize = 9f
                setDrawAxisLine(false)
            }

            setOnChartValueSelectedListener(object : OnChartValueSelectedListener {
                override fun onValueSelected(e: Entry?, h: Highlight?) {
                    val index = e?.x?.toInt() ?: return
                    if (index in cachedCandles.indices) {
                        updateOhlcBanner(cachedCandles[index])
                    }
                }

                override fun onNothingSelected() {
                    if (cachedCandles.isNotEmpty()) {
                        updateOhlcBanner(cachedCandles.last())
                    }
                }
            })
        }
        binding.chartContainer.removeAllViews()
        binding.chartContainer.addView(candleChart)

        // 2. Volume Chart (Sub Pane)
        volumeChart = BarChart(context).apply {
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
            setBackgroundColor(bgColor)
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(true)
            isDragEnabled = true
            setScaleEnabled(true)
            setPinchZoom(true)
            setDrawGridBackground(false)

            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                setDrawGridLines(false)
                setDrawLabels(false)
            }

            axisLeft.isEnabled = false

            axisRight.apply {
                isEnabled = true
                setDrawGridLines(false)
                this.textColor = textColor
                textSize = 8f
                setDrawAxisLine(false)
            }
        }
        binding.volumeContainer.removeAllViews()
        binding.volumeContainer.addView(volumeChart)
    }

    private fun setupListeners() {
        // Back
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        // Timeframes
        val timeframeMap = mapOf(
            binding.tf1d to "1D",
            binding.tf1w to "1W",
            binding.tf1m to "1M",
            binding.tf3m to "3M",
            binding.tf1y to "1Y",
            binding.tfAll to "ALL"
        )
        timeframeMap.forEach { (textView, tf) ->
            textView.setOnClickListener {
                viewModel.setTimeframe(tf)
            }
        }

        // Technical Indicator Toggles
        val indicatorMap = mapOf(
            binding.indMa to "MA",
            binding.indEma to "EMA",
            binding.indBoll to "BOLL",
            binding.indVol to "VOL",
            binding.indRsi to "RSI",
            binding.indMacd to "MACD"
        )
        indicatorMap.forEach { (textView, ind) ->
            textView.setOnClickListener {
                viewModel.toggleIndicator(ind)
            }
        }

        // Drawing Tools
        binding.toolCrosshair.setOnClickListener {
            viewModel.selectTool(DrawingTool.CROSSHAIR)
            Toast.makeText(requireContext(), "Crosshair cursor active: drag on chart to scrub", Toast.LENGTH_SHORT).show()
        }

        binding.toolTrendline.setOnClickListener {
            viewModel.selectTool(DrawingTool.TRENDLINE)
            addTrendlineAnnotation()
        }

        binding.toolHorizontal.setOnClickListener {
            viewModel.selectTool(DrawingTool.HORIZONTAL_RAY)
            addHorizontalSupportRay()
        }

        binding.toolClear.setOnClickListener {
            clearDrawingOverlays()
            viewModel.clearDrawings()
            Toast.makeText(requireContext(), "Chart drawings cleared", Toast.LENGTH_SHORT).show()
        }

        // Retry
        binding.btnRetry.setOnClickListener {
            viewModel.retry()
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is ChartFullscreenUiState.Loading -> {
                            lastBoundDetail = null
                            lastBoundCandles = null
                            lastBoundOhlcCandle = null
                            binding.progressLoading.visibility = View.VISIBLE
                            binding.chartContainer.visibility = View.GONE
                            binding.volumeContainer.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.GONE
                        }
                        is ChartFullscreenUiState.Success -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.chartContainer.visibility = View.VISIBLE
                            binding.layoutErrorState.visibility = View.GONE

                            if (lastBoundDetail != state.stockDetail) {
                                bindHeader(state.stockDetail)
                                lastBoundDetail = state.stockDetail
                            }
                            cachedCandles = state.candles

                            // Tapping an indicator or drawing tool emits a new state with the same
                            // candles; rebuilding the datasets would restart the chart and jump the
                            // viewport back to the newest candle.
                            if (lastBoundCandles != state.candles) {
                                bindCandles(state.candles)
                                // Only memoise once the datasets are really attached; bindCandles
                                // returns early while the charts are still being created.
                                if (candleChart != null && volumeChart != null) {
                                    lastBoundCandles = state.candles
                                }
                            }

                            updateTimeframePills(state.selectedTimeframe)
                            updateIndicatorPills(state.activeIndicators)
                            updateDrawingToolIcons(state.selectedTool)

                            // Toggle volume container visibility based on VOL indicator
                            val showVolume = state.activeIndicators.contains("VOL")
                            binding.volumeContainer.visibility = if (showVolume) View.VISIBLE else View.GONE

                            val latestCandle = state.candles.lastOrNull()
                            if (latestCandle != null && latestCandle != lastBoundOhlcCandle) {
                                updateOhlcBanner(latestCandle)
                                lastBoundOhlcCandle = latestCandle
                            }
                        }
                        is ChartFullscreenUiState.Empty -> {
                            lastBoundDetail = null
                            lastBoundCandles = null
                            lastBoundOhlcCandle = null
                            binding.progressLoading.visibility = View.GONE
                            binding.chartContainer.visibility = View.GONE
                            binding.volumeContainer.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = "No historical candle data found for $symbol"
                        }
                        is ChartFullscreenUiState.Error -> {
                            lastBoundDetail = null
                            lastBoundCandles = null
                            lastBoundOhlcCandle = null
                            binding.progressLoading.visibility = View.GONE
                            binding.chartContainer.visibility = View.GONE
                            binding.volumeContainer.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun bindHeader(detail: StockDetail) {
        binding.tvChartSymbol.text = detail.symbol
        binding.tvChartCompany.text = detail.companyName
        binding.tvChartPrice.text = String.format(Locale.US, "%.2f", detail.price)

        val isPositive = detail.changeAmount >= 0
        val sign = if (isPositive) "+" else ""
        binding.tvChartChange.text = String.format(Locale.US, "%s%.2f%%", sign, detail.changePercent)

        val changeColor = if (isPositive) R.color.color_positive else R.color.color_negative
        val changeBg = if (isPositive) R.drawable.bg_badge_positive else R.drawable.bg_badge_negative

        binding.tvChartPrice.setTextColor(ContextCompat.getColor(requireContext(), changeColor))
        binding.tvChartChange.setTextColor(ContextCompat.getColor(requireContext(), changeColor))
        binding.tvChartChange.setBackgroundResource(changeBg)
    }

    private fun updateOhlcBanner(candle: CandleEntry) {
        val dateStr = ohlcDateFormat.format(java.util.Date(candle.timestamp))
        binding.tvOhlcDate.text = dateStr
        binding.tvOhlcOpen.text = String.format(Locale.US, "O: %.2f", candle.open)
        binding.tvOhlcHigh.text = String.format(Locale.US, "H: %.2f", candle.high)
        binding.tvOhlcLow.text = String.format(Locale.US, "L: %.2f", candle.low)
        binding.tvOhlcClose.text = String.format(Locale.US, "C: %.2f", candle.close)
        binding.tvOhlcVolume.text = String.format(Locale.US, "Vol: %,d", candle.volume)
    }

    private fun bindCandles(candles: List<CandleEntry>) {
        val chart = candleChart ?: return
        val positiveColor = ContextCompat.getColor(requireContext(), R.color.color_positive)
        val negativeColor = ContextCompat.getColor(requireContext(), R.color.color_negative)

        val candleEntries = candles.mapIndexed { index, candle ->
            com.github.mikephil.charting.data.CandleEntry(
                index.toFloat(),
                candle.high,
                candle.low,
                candle.open,
                candle.close
            )
        }

        val dataSet = CandleDataSet(candleEntries, "OHLC").apply {
            setDrawValues(false)
            shadowColorSameAsCandle = true
            increasingColor = positiveColor
            increasingPaintStyle = Paint.Style.FILL
            decreasingColor = negativeColor
            decreasingPaintStyle = Paint.Style.FILL
            neutralColor = Color.GRAY
            shadowWidth = 1.0f
            highlightLineWidth = 1.0f
            highLightColor = ContextCompat.getColor(requireContext(), R.color.color_ai_blue)
        }

        chart.data = CandleData(dataSet)
        chart.setVisibleXRangeMaximum(60f)
        chart.moveViewToX(candleEntries.size.toFloat())
        chart.invalidate()

        // Volume sub-chart
        val volChart = volumeChart ?: return
        val barEntries = candles.mapIndexed { index, candle ->
            BarEntry(index.toFloat(), candle.volume.toFloat())
        }
        val barColors = candles.map { candle ->
            if (candle.close >= candle.open) positiveColor else negativeColor
        }

        val barDataSet = BarDataSet(barEntries, "Volume").apply {
            setDrawValues(false)
            colors = barColors
            highLightColor = ContextCompat.getColor(requireContext(), R.color.color_ai_blue)
        }

        volChart.data = BarData(barDataSet).apply {
            barWidth = 0.8f
        }
        volChart.setVisibleXRangeMaximum(60f)
        volChart.moveViewToX(barEntries.size.toFloat())
        volChart.invalidate()
    }

    private fun addHorizontalSupportRay() {
        val chart = candleChart ?: return
        val price = cachedCandles.lastOrNull()?.close?.toFloat() ?: return

        val limitLine = LimitLine(price, "Ray: %.2f".format(Locale.US, price)).apply {
            lineColor = ContextCompat.getColor(requireContext(), R.color.color_ai_blue)
            lineWidth = 1.5f
            enableDashedLine(12f, 8f, 0f)
            textColor = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
            textSize = 10f
            labelPosition = LimitLine.LimitLabelPosition.RIGHT_TOP
        }

        chart.axisRight.addLimitLine(limitLine)
        chart.invalidate()
        Toast.makeText(requireContext(), "Horizontal Price Ray added at %.2f".format(Locale.US, price), Toast.LENGTH_SHORT).show()
    }

    private fun addTrendlineAnnotation() {
        val chart = candleChart ?: return
        if (cachedCandles.size < 2) return

        val last = cachedCandles.last()
        val prev = cachedCandles[cachedCandles.size - 2]
        val avg = ((last.high + prev.low) / 2f)

        val limitLine = LimitLine(avg, "Trend: %.2f".format(Locale.US, avg)).apply {
            lineColor = ContextCompat.getColor(requireContext(), R.color.color_gold_accent)
            lineWidth = 1.5f
            textColor = ContextCompat.getColor(requireContext(), R.color.color_gold_accent)
            textSize = 10f
            labelPosition = LimitLine.LimitLabelPosition.LEFT_TOP
        }

        chart.axisRight.addLimitLine(limitLine)
        chart.invalidate()
        Toast.makeText(requireContext(), "Trendline benchmark added", Toast.LENGTH_SHORT).show()
    }

    private fun clearDrawingOverlays() {
        candleChart?.axisRight?.removeAllLimitLines()
        candleChart?.highlightValue(null)
        volumeChart?.highlightValue(null)
        candleChart?.invalidate()
        volumeChart?.invalidate()
    }

    private fun updateTimeframePills(selectedTf: String) {
        val pills = listOf(
            binding.tf1d to "1D",
            binding.tf1w to "1W",
            binding.tf1m to "1M",
            binding.tf3m to "3M",
            binding.tf1y to "1Y",
            binding.tfAll to "ALL"
        )

        pills.forEach { (view: TextView, tf: String) ->
            val isSelected = selectedTf.equals(tf, ignoreCase = true)
            if (isSelected) {
                view.setBackgroundResource(R.drawable.bg_chip_filter_selected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))
            } else {
                view.setBackgroundResource(R.drawable.bg_chip_filter_unselected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
            }
        }
    }

    private fun updateIndicatorPills(activeSet: Set<String>) {
        val indicators = listOf(
            binding.indMa to "MA",
            binding.indEma to "EMA",
            binding.indBoll to "BOLL",
            binding.indVol to "VOL",
            binding.indRsi to "RSI",
            binding.indMacd to "MACD"
        )

        indicators.forEach { (view: TextView, ind: String) ->
            val isActive = activeSet.contains(ind)
            if (isActive) {
                view.setBackgroundResource(R.drawable.bg_chip_filter_selected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))
            } else {
                view.setBackgroundResource(R.drawable.bg_chip_filter_unselected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
            }
        }
    }

    private fun updateDrawingToolIcons(selectedTool: DrawingTool) {
        val activeColor = ContextCompat.getColor(requireContext(), R.color.color_positive)
        val inactiveColor = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        binding.toolCrosshair.setColorFilter(if (selectedTool == DrawingTool.CROSSHAIR) activeColor else inactiveColor)
        binding.toolTrendline.setColorFilter(if (selectedTool == DrawingTool.TRENDLINE) activeColor else inactiveColor)
        binding.toolHorizontal.setColorFilter(if (selectedTool == DrawingTool.HORIZONTAL_RAY) activeColor else inactiveColor)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
        candleChart = null
        volumeChart = null
    }
}
