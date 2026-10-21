package com.fyp.basarattradeinvest.feature.recommendation.smartselection

import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Paint
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentSmartSelectionBinding
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationSignal
import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import com.github.mikephil.charting.charts.CandleStickChart
import com.github.mikephil.charting.components.LimitLine
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.CandleData
import com.github.mikephil.charting.data.CandleDataSet
import com.github.mikephil.charting.data.CandleEntry as ChartCandleEntry
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter
import com.github.mikephil.charting.formatter.ValueFormatter
import com.google.android.material.chip.Chip
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class SmartSelectionFragment : Fragment() {

    private var _binding: FragmentSmartSelectionBinding? = null
    private val binding get() = _binding!!
    private val viewModel: SmartSelectionViewModel by activityViewModels()

    private var priceChart: CandleStickChart? = null
    private var renderedCandidates: List<String> = emptyList()
    private var renderedSetup: SmartSelectionSetup? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentSmartSelectionBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupToolbar()
        setupChart()
        binding.btnRetry.setOnClickListener { viewModel.retry() }
        observeState()
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            findNavController().popBackStack()
        }
    }

    private fun setupChart() {
        val chart = CandleStickChart(requireContext()).apply {
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(true)
            isDragEnabled = true
            setScaleEnabled(true)
            setPinchZoom(true)
            setDrawGridBackground(false)
            setBackgroundColor(Color.TRANSPARENT)
            setNoDataTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
            setNoDataText(getString(R.string.smart_selection_chart_unavailable))

            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                setDrawGridLines(false)
                textColor = ContextCompat.getColor(requireContext(), R.color.color_text_tertiary)
                textSize = 9f
                granularity = 1f
            }
            axisLeft.isEnabled = false
            axisRight.apply {
                isEnabled = true
                setDrawGridLines(true)
                gridColor = ContextCompat.getColor(requireContext(), R.color.color_divider)
                textColor = ContextCompat.getColor(requireContext(), R.color.color_text_tertiary)
                textSize = 9f
                setDrawAxisLine(false)
                valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String =
                        String.format(Locale.US, "%.1f", value)
                }
            }
        }
        priceChart = chart
        binding.chartContainer.addView(
            chart,
            ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        )
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect(::renderState)
            }
        }
    }

    private fun renderState(state: SmartSelectionUiState) {
        val hasCandidates = state.candidates.isNotEmpty()
        binding.layoutSmartContent.visibility = if (hasCandidates) View.VISIBLE else View.GONE
        binding.layoutStatus.visibility = if (hasCandidates) View.GONE else View.VISIBLE
        binding.progressCandidates.visibility =
            if (state.isLoadingCandidates) View.VISIBLE else View.GONE
        binding.tvStatus.visibility = if (state.isLoadingCandidates) View.GONE else View.VISIBLE
        binding.btnRetry.visibility = if (state.isLoadingCandidates) View.GONE else View.VISIBLE

        if (!hasCandidates) {
            binding.tvStatus.text = state.candidatesError
                ?: getString(R.string.smart_selection_no_candidates)
            return
        }

        val symbols = state.candidates.map { it.symbol }
        if (symbols != renderedCandidates) {
            renderCandidateChips(state.candidates)
            renderedCandidates = symbols
        }

        val selected = state.candidates.firstOrNull { it.symbol == state.selectedSymbol }
        binding.tvSelectedSymbol.text = selected?.symbol.orEmpty()
        bindSignal(selected?.signal)

        val setup = state.selectedSetup
        if (setup == null) {
            binding.tvCurrentPrice.text = getString(R.string.smart_selection_current_price) + " · --"
            binding.tvTargetPrice.text = "--"
            binding.tvStopLoss.text = "--"
            binding.tvConfidence.text = selected?.let {
                getString(R.string.smart_selection_confidence, (it.confidence * 100).toInt())
            }.orEmpty()
            binding.tvSummary.text = selected?.summary.orEmpty()
            bindBreakout(null)
            if (renderedSetup != null) clearChart()
        } else {
            if (setup != renderedSetup) {
                bindChart(setup.candles, setup.currentPrice, setup.targetPrice, setup.stopLoss, setup.breakout)
                bindBreakout(setup.breakout)
                renderedSetup = setup
            }
            binding.tvCurrentPrice.text = setup.currentPrice?.let {
                String.format(
                    Locale.US,
                    "%s · PKR %.2f",
                    getString(R.string.smart_selection_current_price),
                    it
                )
            } ?: (getString(R.string.smart_selection_current_price) + " · --")
            binding.tvTargetPrice.text = setup.targetPrice?.let {
                String.format(Locale.US, "PKR %.2f", it)
            } ?: "--"
            binding.tvStopLoss.text = setup.stopLoss?.let {
                String.format(Locale.US, "PKR %.2f", it)
            } ?: "--"
            binding.tvConfidence.text = getString(
                R.string.smart_selection_confidence,
                (setup.recommendation.confidence * 100).toInt()
            )
            binding.tvSummary.text = setup.recommendation.summary
        }

        binding.progressSetup.visibility = if (state.isLoadingSetup) View.VISIBLE else View.GONE
        binding.tvSetupMessage.text = state.setupMessage.orEmpty()
        binding.tvSetupMessage.visibility = if (state.setupMessage.isNullOrBlank()) View.GONE else View.VISIBLE
    }

    private fun renderCandidateChips(candidates: List<StockRecommendation>) {
        binding.chipGroupStocks.removeAllViews()
        val states = arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf())
        val backgroundColors = intArrayOf(
            ContextCompat.getColor(requireContext(), R.color.color_chip_selected_bg),
            ContextCompat.getColor(requireContext(), R.color.color_surface)
        )
        val textColors = intArrayOf(
            ContextCompat.getColor(requireContext(), R.color.color_positive),
            ContextCompat.getColor(requireContext(), R.color.color_text_secondary)
        )
        val strokeColors = intArrayOf(
            ContextCompat.getColor(requireContext(), R.color.color_chip_selected_stroke),
            ContextCompat.getColor(requireContext(), R.color.color_divider)
        )

        candidates.forEach { recommendation ->
            val chip = Chip(requireContext()).apply {
                text = recommendation.symbol
                isCheckable = true
                isChecked = recommendation.symbol == viewModel.uiState.value.selectedSymbol
                textSize = 12f
                chipMinHeight = resources.displayMetrics.density * 36f
                chipCornerRadius = resources.displayMetrics.density * 20f
                chipBackgroundColor = ColorStateList(states, backgroundColors)
                setTextColor(ColorStateList(states, textColors))
                chipStrokeColor = ColorStateList(states, strokeColors)
                chipStrokeWidth = resources.displayMetrics.density
                setOnClickListener { viewModel.selectStock(recommendation.symbol) }
            }
            binding.chipGroupStocks.addView(chip)
        }
    }

    private fun bindSignal(signal: RecommendationSignal?) {
        val (background, tint, label) = when (signal ?: RecommendationSignal.HOLD) {
            RecommendationSignal.BUY -> Triple(
                R.drawable.bg_badge_positive,
                R.color.color_positive,
                RecommendationSignal.BUY.label
            )
            RecommendationSignal.SELL -> Triple(
                R.drawable.bg_badge_negative,
                R.color.color_negative,
                RecommendationSignal.SELL.label
            )
            RecommendationSignal.HOLD -> Triple(
                R.drawable.bg_badge_neutral,
                R.color.color_neutral,
                RecommendationSignal.HOLD.label
            )
        }
        binding.tvSignalBadge.text = label
        binding.tvSignalBadge.setBackgroundResource(background)
        binding.tvSignalBadge.setTextColor(ContextCompat.getColor(requireContext(), tint))
    }

    private fun bindChart(
        candles: List<CandleEntry>,
        currentPrice: Double?,
        targetPrice: Double?,
        stopLoss: Double?,
        breakout: BreakoutLevels?
    ) {
        val chart = priceChart ?: return
        if (candles.isEmpty()) {
            clearChart()
            return
        }

        val positiveColor = ContextCompat.getColor(requireContext(), R.color.color_positive)
        val negativeColor = ContextCompat.getColor(requireContext(), R.color.color_negative)
        val entries = candles.mapIndexed { index, candle ->
            ChartCandleEntry(
                index.toFloat(),
                candle.high,
                candle.low,
                candle.open,
                candle.close
            )
        }
        val dataSet = CandleDataSet(entries, "Price").apply {
            setDrawValues(false)
            shadowColorSameAsCandle = true
            increasingColor = positiveColor
            increasingPaintStyle = Paint.Style.FILL
            decreasingColor = negativeColor
            decreasingPaintStyle = Paint.Style.FILL
            neutralColor = ContextCompat.getColor(requireContext(), R.color.color_text_tertiary)
            shadowWidth = 1f
        }
        chart.data = CandleData(dataSet)
        val axisLabelFormat = SimpleDateFormat("dd/MM", Locale.getDefault())
        chart.xAxis.valueFormatter = IndexAxisValueFormatter(
            candles.map { candle -> axisLabelFormat.format(Date(candle.timestamp)) }
        )

        val axis = chart.axisRight
        axis.removeAllLimitLines()
        val allLevels = buildList {
            candles.forEach { add(it.high.toDouble()); add(it.low.toDouble()) }
            currentPrice?.takeIf { it > 0.0 }?.let { add(it) }
            targetPrice?.takeIf { it > 0.0 }?.let { add(it) }
            stopLoss?.takeIf { it > 0.0 }?.let { add(it) }
        }
        val low = allLevels.minOrNull() ?: 0.0
        val high = allLevels.maxOrNull() ?: 1.0
        val padding = ((high - low).coerceAtLeast(high * 0.02)) * 0.08
        axis.axisMinimum = (low - padding).toFloat().coerceAtLeast(0f)
        axis.axisMaximum = (high + padding).toFloat()

        targetPrice?.takeIf { it > 0.0 }?.let {
            axis.addLimitLine(createLevelLine(
                it,
                getString(R.string.smart_selection_live_target, it),
                positiveColor
            ))
        }
        stopLoss?.takeIf { it > 0.0 }?.let {
            axis.addLimitLine(createLevelLine(
                it,
                getString(R.string.smart_selection_live_stop, it),
                negativeColor
            ))
        }
        currentPrice?.takeIf { it > 0.0 }?.let {
            axis.addLimitLine(createLevelLine(
                it,
                String.format(Locale.US, "Current · %.2f", it),
                ContextCompat.getColor(requireContext(), R.color.color_text_secondary)
            ))
        }

        breakout?.let { levels ->
            axis.addLimitLine(createLevelLine(
                levels.resistance,
                getString(R.string.smart_selection_breakout_line, levels.resistance),
                ContextCompat.getColor(requireContext(), R.color.color_gold_accent)
            ))
            axis.addLimitLine(createLevelLine(
                levels.support,
                getString(R.string.smart_selection_breakdown_line, levels.support),
                ContextCompat.getColor(requireContext(), R.color.color_neutral),
                labelPosition = LimitLine.LimitLabelPosition.RIGHT_BOTTOM
            ))
        }

        chart.setVisibleXRangeMaximum(minOf(30f, entries.size.toFloat().coerceAtLeast(5f)))
        chart.moveViewToX(entries.size.toFloat())
        chart.notifyDataSetChanged()
        chart.invalidate()
    }

    private fun bindBreakout(breakout: BreakoutLevels?) {
        if (breakout == null) {
            binding.tvBreakoutLevels.visibility = View.GONE
            binding.tvBreakoutStatus.visibility = View.GONE
            return
        }

        binding.tvBreakoutLevels.text = getString(
            R.string.smart_selection_breakout_levels,
            breakout.resistance,
            breakout.support
        )
        binding.tvBreakoutStatus.text = when {
            breakout.isConfirmed -> getString(R.string.smart_selection_breakout_confirmed, breakout.volumeRatio)
            breakout.distanceToBreakoutPct > 0.0 ->
                getString(R.string.smart_selection_breakout_below, breakout.distanceToBreakoutPct)
            else ->
                getString(R.string.smart_selection_breakout_above, -breakout.distanceToBreakoutPct)
        }
        binding.tvBreakoutLevels.visibility = View.VISIBLE
        binding.tvBreakoutStatus.visibility = View.VISIBLE
    }

    private fun createLevelLine(
        value: Double,
        label: String,
        color: Int,
        labelPosition: LimitLine.LimitLabelPosition = LimitLine.LimitLabelPosition.RIGHT_TOP
    ): LimitLine =
        LimitLine(value.toFloat(), label).apply {
            lineColor = color
            lineWidth = 1.2f
            textColor = color
            textSize = 8f
            this.labelPosition = labelPosition
            enableDashedLine(6f, 4f, 0f)
        }

    private fun clearChart() {
        priceChart?.apply {
            data = null
            axisRight.removeAllLimitLines()
            invalidate()
        }
        renderedSetup = null
    }

    override fun onDestroyView() {
        super.onDestroyView()
        priceChart = null
        renderedSetup = null
        renderedCandidates = emptyList()
        _binding = null
    }
}
