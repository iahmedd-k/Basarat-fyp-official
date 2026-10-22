package com.fyp.basarattradeinvest.feature.portfolio.main

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.core.os.bundleOf
import androidx.core.widget.doAfterTextChanged
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentPortfolioMainBinding
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPerformance
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPnL
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import com.fyp.basarattradeinvest.feature.portfolio.main.adapter.AllocationBarAdapter
import com.fyp.basarattradeinvest.feature.portfolio.main.adapter.AllocationDisplayItem
import com.fyp.basarattradeinvest.feature.portfolio.main.adapter.HoldingAdapter
import com.fyp.basarattradeinvest.feature.portfolio.transactions.adapter.TransactionAdapter
import com.fyp.basarattradeinvest.feature.portfolio.transactions.dialog.AddEditTransactionDialogFragment
import com.fyp.basarattradeinvest.feature.portfolio.transactions.dialog.RecordCompletedTradeDialogFragment
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.data.PieData
import com.github.mikephil.charting.data.PieDataSet
import com.github.mikephil.charting.data.PieEntry
import com.github.mikephil.charting.formatter.ValueFormatter
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

class PortfolioMainFragment : Fragment() {

    private var _binding: FragmentPortfolioMainBinding? = null
    private val binding get() = _binding!!
    private var lastRenderedSuccess: PortfolioMainUiState.Success? = null

    private val viewModel: PortfolioMainViewModel by activityViewModels { PortfolioMainViewModel.Factory() }

    private lateinit var holdingAdapter: HoldingAdapter
    private lateinit var stockAllocationAdapter: AllocationBarAdapter
    private lateinit var sectorAllocationAdapter: AllocationBarAdapter
    private lateinit var transactionAdapter: TransactionAdapter

    private var originalHoldings: List<HoldingItem> = emptyList()
    private var currentFilterMode: String = "ALL" // "ALL", "PROFIT", "LOSS"
    private var currentSearchQuery: String = ""

    // Privacy toggle state
    private var isBalanceHidden: Boolean = false
    private var lastCurrentValue: Double = 0.0
    private var lastTotalPnl: Double = 0.0
    private var lastTotalPnlPercent: Double = 0.0
    private var lastTodayPnl: Double = 0.0

    // Selected chart view mode: 0: Line Chart, 1: Pie Chart, 2: Statistics
    private var currentChartMode: Int = 0

    private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentPortfolioMainBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerViews()
        setupPerformanceLineChart()
        setupAllocationChart()
        setupChartModeToggle()
        setupPrivacyToggle()
        setupTimeframeChips()
        setupHoldingsSearchAndFilter()
        setupListeners()
        observeState()
        viewModel.ensureLoaded()
    }

    override fun onResume() {
        super.onResume()
        val handle = findNavController().currentBackStackEntry?.savedStateHandle ?: return
        if (handle.get<Boolean>(com.fyp.basarattradeinvest.feature.portfolio.transactions.TransactionDetailFragment.PORTFOLIO_CHANGED_KEY) == true) {
            handle.remove<Boolean>(com.fyp.basarattradeinvest.feature.portfolio.transactions.TransactionDetailFragment.PORTFOLIO_CHANGED_KEY)
            viewModel.loadPortfolio(forceRefresh = true)
        }
    }

    private fun setupRecyclerViews() {
        holdingAdapter = HoldingAdapter { symbol ->
            val bundle = bundleOf("symbol" to symbol)
            findNavController().navigate(R.id.action_portfolio_to_holdingDetail, bundle)
        }
        binding.rvHoldings.layoutManager = LinearLayoutManager(requireContext())
        binding.rvHoldings.adapter = holdingAdapter

        stockAllocationAdapter = AllocationBarAdapter()
        binding.rvAllocationStock.layoutManager = LinearLayoutManager(requireContext())
        binding.rvAllocationStock.adapter = stockAllocationAdapter

        sectorAllocationAdapter = AllocationBarAdapter()
        binding.rvAllocationSector.layoutManager = LinearLayoutManager(requireContext())
        binding.rvAllocationSector.adapter = sectorAllocationAdapter

        transactionAdapter = TransactionAdapter { txId ->
            val bundle = bundleOf("transaction_id" to txId)
            findNavController().navigate(R.id.action_portfolio_to_transactionDetail, bundle)
        }
        binding.rvRecentTransactions.layoutManager = LinearLayoutManager(requireContext())
        binding.rvRecentTransactions.adapter = transactionAdapter
    }

    private fun setupPerformanceLineChart() {
        binding.chartPortfolioPerformance.apply {
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(true)
            isDragEnabled = true
            setScaleEnabled(false)
            setPinchZoom(false)
            setDrawGridBackground(false)
            setViewPortOffsets(48f, 16f, 16f, 28f)

            // X Axis
            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                setDrawGridLines(false)
                setDrawAxisLine(false)
                textColor = ContextCompat.getColor(requireContext(), R.color.color_text_tertiary)
                textSize = 9f
                granularity = 1f
            }

            // Left Axis
            axisLeft.apply {
                setDrawGridLines(true)
                gridColor = ContextCompat.getColor(requireContext(), R.color.color_divider)
                gridLineWidth = 0.8f
                setDrawAxisLine(false)
                textColor = ContextCompat.getColor(requireContext(), R.color.color_text_tertiary)
                textSize = 9f
                valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String {
                        return if (value >= 1_000_000f) {
                            String.format(Locale.US, "%.1f M", value / 1_000_000f)
                        } else if (value >= 1_000f) {
                            String.format(Locale.US, "%.0f k", value / 1_000f)
                        } else {
                            String.format(Locale.US, "%.0f", value)
                        }
                    }
                }
            }

            // Right Axis
            axisRight.isEnabled = false
            setNoDataText("")
            setNoDataTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_tertiary))
        }
        renderPerformanceLineChart(null)
    }

    private fun setupAllocationChart() {
        binding.chartStockAllocation.apply {
            setUsePercentValues(true)
            description.isEnabled = false
            setExtraOffsets(6f, 10f, 6f, 6f)
            dragDecelerationFrictionCoef = 0.95f
            isDrawHoleEnabled = true
            setHoleColor(Color.TRANSPARENT)
            setTransparentCircleColor(Color.TRANSPARENT)
            setTransparentCircleAlpha(110)
            holeRadius = 58f
            transparentCircleRadius = 62f
            setDrawCenterText(true)
            centerText = "Portfolio\nAllocation"
            setCenterTextSize(12f)
            setCenterTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_primary))
            rotationAngle = 0f
            isRotationEnabled = true
            isHighlightPerTapEnabled = true
            legend.isEnabled = false
            setEntryLabelColor(Color.TRANSPARENT)
            setNoDataText("No stock allocation data available")
            setNoDataTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_tertiary))
        }
    }

    private fun setupChartModeToggle() {
        binding.btnModeLineChart.setOnClickListener { switchChartMode(0) }
        binding.btnModePieChart.setOnClickListener { switchChartMode(1) }
        binding.btnModeStatistics.setOnClickListener { switchChartMode(2) }
    }

    private fun switchChartMode(mode: Int) {
        currentChartMode = mode
        val selectedBg = R.drawable.bg_pill_chart_toggle_selected
        val unselectedBg = R.drawable.bg_pill_chart_toggle_unselected
        val primaryText = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val secondaryText = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        // Line Chart Mode
        binding.btnModeLineChart.setBackgroundResource(if (mode == 0) selectedBg else unselectedBg)
        binding.tvModeLineText.setTextColor(if (mode == 0) primaryText else secondaryText)
        binding.ivModeLineIcon.setColorFilter(if (mode == 0) primaryText else secondaryText)
        binding.containerLineChart.visibility = if (mode == 0) View.VISIBLE else View.GONE

        // Pie Chart Mode
        binding.btnModePieChart.setBackgroundResource(if (mode == 1) selectedBg else unselectedBg)
        binding.tvModePieText.setTextColor(if (mode == 1) primaryText else secondaryText)
        binding.ivModePieIcon.setColorFilter(if (mode == 1) primaryText else secondaryText)
        binding.containerPieChart.visibility = if (mode == 1) View.VISIBLE else View.GONE

        // Statistics Mode
        binding.btnModeStatistics.setBackgroundResource(if (mode == 2) selectedBg else unselectedBg)
        binding.tvModeStatsText.setTextColor(if (mode == 2) primaryText else secondaryText)
        binding.ivModeStatsIcon.setColorFilter(if (mode == 2) primaryText else secondaryText)
        binding.containerStatistics.visibility = if (mode == 2) View.VISIBLE else View.GONE
    }

    private fun setupPrivacyToggle() {
        binding.ivBalancePrivacyToggle.setOnClickListener {
            isBalanceHidden = !isBalanceHidden
            binding.ivBalancePrivacyToggle.setImageResource(
                if (isBalanceHidden) R.drawable.ic_eye_closed else R.drawable.ic_eye_open
            )
            renderBalanceValues()
        }
    }

    private fun renderBalanceValues() {
        if (isBalanceHidden) {
            binding.tvTotalCurrentValue.text = "PKR ••••••"
            binding.tvTodayPnl.text = "+PKR •••• (24h)"
        } else {
            binding.tvTotalCurrentValue.text = "PKR ${currencyFormat.format(lastCurrentValue)}"
            val todayPrefix = if (lastTodayPnl >= 0) "+" else ""
            binding.tvTodayPnl.text = "${todayPrefix}PKR ${currencyFormat.format(lastTodayPnl)} (24h)"
        }

        val prefix = if (lastTotalPnl >= 0) "▲ " else "▼ "
        binding.tvTotalPnlBadge.text = String.format(
            Locale.US,
            "%s%.2f%%",
            prefix,
            kotlin.math.abs(lastTotalPnlPercent)
        )
        if (lastTotalPnl >= 0) {
            binding.tvTotalPnlBadge.setBackgroundResource(R.drawable.bg_badge_buy)
            binding.tvTotalPnlBadge.setTextColor(Color.parseColor("#18B981"))
        } else {
            binding.tvTotalPnlBadge.setBackgroundResource(R.drawable.bg_badge_sell)
            binding.tvTotalPnlBadge.setTextColor(Color.parseColor("#EF4444"))
        }
    }

    private fun setupTimeframeChips() {
        val chipMap = mapOf(
            binding.btnTf24h to "1D",
            binding.btnTf7d to "1W",
            binding.btnTf30d to "1M",
            binding.btnTf60d to "2M",
            binding.btnTf90d to "3M",
            binding.btnTfAll to "ALL"
        )

        chipMap.forEach { (chip, period) ->
            chip.setOnClickListener {
                highlightTimeframeChip(chip)
                viewModel.setPeriod(period)
            }
        }
    }

    private fun highlightTimeframeChip(activeChip: View) {
        val allChips = listOf(
            binding.btnTf24h,
            binding.btnTf7d,
            binding.btnTf30d,
            binding.btnTf60d,
            binding.btnTf90d,
            binding.btnTfAll
        )
        val selectedBg = R.drawable.bg_timeframe_chip_selected
        val unselectedBg = R.drawable.bg_timeframe_chip_unselected
        val primaryText = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val secondaryText = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        allChips.forEach { chip ->
            val isCurrent = chip == activeChip
            chip.setBackgroundResource(if (isCurrent) selectedBg else unselectedBg)
            chip.setTextColor(if (isCurrent) primaryText else secondaryText)
        }
    }

    private fun setupHoldingsSearchAndFilter() {
        binding.etSearchHoldings.doAfterTextChanged { text ->
            currentSearchQuery = text?.toString()?.trim() ?: ""
            binding.btnClearHoldingsSearch.visibility = if (currentSearchQuery.isNotEmpty()) View.VISIBLE else View.GONE
            filterAndSubmitHoldings()
        }

        binding.btnClearHoldingsSearch.setOnClickListener {
            binding.etSearchHoldings.text?.clear()
        }

        binding.chipFilterAll.setOnClickListener {
            setHoldingsFilter("ALL")
        }

        binding.chipFilterProfit.setOnClickListener {
            setHoldingsFilter("PROFIT")
        }

        binding.chipFilterLoss.setOnClickListener {
            setHoldingsFilter("LOSS")
        }
    }

    private fun setHoldingsFilter(mode: String) {
        if (currentFilterMode == mode) return
        currentFilterMode = mode

        val activeBg = R.drawable.bg_timeframe_active
        val inactiveBg = R.drawable.bg_tab_unselected
        val activeTextColor = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val inactiveTextColor = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        binding.chipFilterAll.setBackgroundResource(if (mode == "ALL") activeBg else inactiveBg)
        binding.chipFilterAll.setTextColor(if (mode == "ALL") activeTextColor else inactiveTextColor)

        binding.chipFilterProfit.setBackgroundResource(if (mode == "PROFIT") activeBg else inactiveBg)
        binding.chipFilterProfit.setTextColor(if (mode == "PROFIT") activeTextColor else inactiveTextColor)

        binding.chipFilterLoss.setBackgroundResource(if (mode == "LOSS") activeBg else inactiveBg)
        binding.chipFilterLoss.setTextColor(if (mode == "LOSS") activeTextColor else inactiveTextColor)

        filterAndSubmitHoldings()
    }

    private fun filterAndSubmitHoldings() {
        if (originalHoldings.isEmpty()) {
            binding.layoutEmptyHoldings.visibility = View.VISIBLE
            binding.rvHoldings.visibility = View.GONE
            return
        }

        var filtered = originalHoldings

        if (currentSearchQuery.isNotEmpty()) {
            filtered = filtered.filter {
                it.symbol.contains(currentSearchQuery, ignoreCase = true) ||
                it.companyName.contains(currentSearchQuery, ignoreCase = true) ||
                it.sector.contains(currentSearchQuery, ignoreCase = true)
            }
        }

        filtered = when (currentFilterMode) {
            "PROFIT" -> filtered.filter { (it.unrealizedPnl ?: 0.0) >= 0.0 }
            "LOSS" -> filtered.filter { (it.unrealizedPnl ?: 0.0) < 0.0 }
            else -> filtered
        }

        if (filtered.isEmpty()) {
            binding.layoutEmptyHoldings.visibility = View.VISIBLE
            binding.rvHoldings.visibility = View.GONE
        } else {
            binding.layoutEmptyHoldings.visibility = View.GONE
            binding.rvHoldings.visibility = View.VISIBLE
            holdingAdapter.submitList(filtered)
        }
    }

    private fun setupListeners() {
        binding.btnAddTransaction.setOnClickListener {
            val dialog = AddEditTransactionDialogFragment.newInstanceForCreate()
            dialog.onTransactionSaved = {
                viewModel.loadPortfolio(forceRefresh = true)
            }
            dialog.show(childFragmentManager, "add_transaction")
        }

        binding.btnRecordTrade.setOnClickListener {
            val dialog = RecordCompletedTradeDialogFragment()
            dialog.onTradeRecorded = {
                viewModel.loadPortfolio(forceRefresh = true)
            }
            dialog.show(childFragmentManager, "record_trade")
        }

        binding.btnViewFullHistory.setOnClickListener {
            findNavController().navigate(R.id.action_portfolio_to_transactionHistory)
        }

        binding.btnRetry.setOnClickListener {
            viewModel.loadPortfolio(forceRefresh = true)
        }

        binding.btnOpenRiskAnalytics.setOnClickListener {
            findNavController().navigate(R.id.action_portfolio_to_riskAnalytics)
        }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    viewModel.uiState.collect { state ->
                        renderState(state)
                    }
                }
                launch {
                    viewModel.selectedPeriod.collect { period ->
                        val chip = when (period) {
                            "1D" -> binding.btnTf24h
                            "1W" -> binding.btnTf7d
                            "1M" -> binding.btnTf30d
                            "2M" -> binding.btnTf60d
                            "3M" -> binding.btnTf90d
                            "ALL" -> binding.btnTfAll
                            else -> binding.btnTf30d
                        }
                        highlightTimeframeChip(chip)
                    }
                }
            }
        }
    }

    private fun renderState(state: PortfolioMainUiState) {
        when (state) {
            is PortfolioMainUiState.Loading -> {
                lastRenderedSuccess = null
                binding.scrollContent.visibility = View.GONE
                binding.layoutLoading.visibility = View.VISIBLE
                binding.layoutError.visibility = View.GONE
            }
            is PortfolioMainUiState.Success -> {
                binding.scrollContent.visibility = View.VISIBLE
                binding.layoutLoading.visibility = View.GONE
                binding.layoutError.visibility = View.GONE
                binding.layoutRefreshingPortfolio.visibility = if (state.isRefreshing) View.VISIBLE else View.GONE
                val previous = lastRenderedSuccess
                if (previous == null || previous.overview != state.overview) {
                    renderOverview(state.overview)
                }
                if (state.pnl != null && previous?.pnl != state.pnl) {
                    renderPnL(state.pnl)
                }
                if (state.allocation != null && previous?.allocation != state.allocation) {
                    renderAllocation(state.allocation)
                }
                if (previous == null || previous.performance != state.performance) {
                    renderPerformanceLineChart(state.performance)
                }
                if (previous == null || previous.recentTransactions != state.recentTransactions) {
                    renderRecentTransactions(state.recentTransactions)
                }
                lastRenderedSuccess = state
            }
            is PortfolioMainUiState.Empty -> {
                lastRenderedSuccess = null
                binding.layoutRefreshingPortfolio.visibility = View.GONE
                binding.scrollContent.visibility = View.VISIBLE
                binding.layoutLoading.visibility = View.GONE
                binding.layoutError.visibility = View.GONE
                lastCurrentValue = 0.0
                lastTotalPnl = 0.0
                lastTotalPnlPercent = 0.0
                lastTodayPnl = 0.0
                renderBalanceValues()
                binding.tvTotalInvested.text = "PKR 0.00"
                binding.tvHoldingCount.text = "0 Stocks"
                binding.layoutEmptyHoldings.visibility = View.VISIBLE
                binding.rvHoldings.visibility = View.GONE
                renderPerformanceLineChart(null)
            }
            is PortfolioMainUiState.Error -> {
                lastRenderedSuccess = null
                binding.layoutRefreshingPortfolio.visibility = View.GONE
                binding.scrollContent.visibility = View.GONE
                binding.layoutLoading.visibility = View.GONE
                binding.layoutError.visibility = View.VISIBLE
                binding.tvErrorMsg.text = state.message
            }
        }
    }

    private fun renderOverview(overview: PortfolioOverview) {
        val s = overview.summary
        lastCurrentValue = s.currentValue
        lastTotalPnl = s.totalPnl
        lastTotalPnlPercent = s.totalPnlPercent
        lastTodayPnl = s.todayPnl

        renderBalanceValues()

        binding.tvTotalInvested.text = "PKR ${currencyFormat.format(s.totalInvested)}"
        binding.tvHoldingCount.text = "${overview.holdings.size} Stocks"

        originalHoldings = overview.holdings
        filterAndSubmitHoldings()
    }

    private fun renderPerformanceLineChart(perf: PortfolioPerformance?) {
        val points = perf?.data ?: emptyList()
        val entries = ArrayList<Entry>()

        if (points.isEmpty()) {
            binding.chartPortfolioPerformance.clear()
            return
        }

        points.forEachIndexed { index, point ->
            entries.add(Entry(index.toFloat(), point.value.toFloat()))
        }

        if (entries.isEmpty()) {
            binding.chartPortfolioPerformance.clear()
            return
        }

        // Direction of the window being plotted, so a falling curve cannot read as a
        // gain. Lifetime P/L is shown separately in the header.
        val trendColor = ContextCompat.getColor(
            requireContext(),
            if (entries.last().y >= entries.first().y) R.color.color_positive else R.color.color_negative
        )

        val dataSet = LineDataSet(entries, "Portfolio Performance").apply {
            mode = LineDataSet.Mode.CUBIC_BEZIER
            cubicIntensity = 0.2f
            setDrawCircles(false)
            setDrawValues(false)
            lineWidth = 2.5f
            color = trendColor

            setDrawFilled(true)
            fillColor = trendColor
            fillAlpha = 45

            setDrawHighlightIndicators(true)
            setDrawHorizontalHighlightIndicator(false)
            highLightColor = trendColor
            highlightLineWidth = 1.2f
            enableDashedHighlightLine(10f, 5f, 0f)
        }

        binding.chartPortfolioPerformance.data = LineData(dataSet)
        binding.chartPortfolioPerformance.animateX(500)
        binding.chartPortfolioPerformance.invalidate()
    }

    private fun renderPnL(pnl: PortfolioPnL) {
        binding.tvPnlRealized.text = "PKR ${currencyFormat.format(pnl.realizedPnl)}"
        binding.tvPnlUnrealized.text = "PKR ${currencyFormat.format(pnl.unrealizedPnl)}"
    }

    private fun renderAllocation(allocation: PortfolioAllocation) {
        val stockItems = allocation.byStock.map {
            AllocationDisplayItem(it.symbol, it.percentage, it.marketValue)
        }
        stockAllocationAdapter.submitList(stockItems)

        if (allocation.byStock.isNotEmpty()) {
            val pieEntries = allocation.byStock.map {
                PieEntry(it.percentage.toFloat(), it.symbol)
            }
            val chartPalette = listOf(
                Color.parseColor("#00B894"), // BASARAT Green
                Color.parseColor("#4F7CFF"), // AI Blue
                Color.parseColor("#7C6FE8"), // AI Purple
                Color.parseColor("#D4A84F"), // Gold
                Color.parseColor("#14A89B"), // Teal
                Color.parseColor("#F59E0B"), // Amber
                Color.parseColor("#EC4899"), // Pink
                Color.parseColor("#06B6D4"), // Cyan
                Color.parseColor("#10B981"), // Emerald
                Color.parseColor("#6366F1")  // Indigo
            )
            val dataSet = PieDataSet(pieEntries, "Stock Allocation").apply {
                colors = chartPalette
                sliceSpace = 3f
                selectionShift = 5f
                setDrawValues(false)
            }
            binding.chartStockAllocation.data = PieData(dataSet)
            binding.chartStockAllocation.animateY(600)
            binding.chartStockAllocation.invalidate()
        }

        val sectorItems = allocation.bySector.map {
            AllocationDisplayItem(it.sector, it.percentage, it.marketValue)
        }
        sectorAllocationAdapter.submitList(sectorItems)
    }

    private fun renderRecentTransactions(transactions: List<PortfolioTransaction>) {
        transactionAdapter.submitList(transactions)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        lastRenderedSuccess = null
        _binding = null
    }
}
