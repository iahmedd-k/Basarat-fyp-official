package com.fyp.basarattradeinvest.feature.etf

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
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentEtfDetailBinding
import com.fyp.basarattradeinvest.databinding.ItemDetailLabelValueBinding
import com.fyp.basarattradeinvest.databinding.ItemEtfPerformanceRowBinding
import com.fyp.basarattradeinvest.domain.model.etf.EtfItem
import com.fyp.basarattradeinvest.domain.model.etf.EtfPerformance
import com.fyp.basarattradeinvest.domain.model.etf.EtfReturns
import com.fyp.basarattradeinvest.feature.common.FormatUtils
import com.fyp.basarattradeinvest.feature.etf.adapter.EtfHistoryAdapter
import kotlinx.coroutines.launch
import java.util.Locale

class EtfDetailFragment : Fragment() {

    private var _binding: FragmentEtfDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: EtfDetailViewModel by activityViewModels()

    private val historyAdapter by lazy { EtfHistoryAdapter() }

    private var symbol: String = ""

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentEtfDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        symbol = arguments?.getString("symbol").orEmpty()

        binding.rvHistory.layoutManager = LinearLayoutManager(requireContext())
        binding.rvHistory.adapter = historyAdapter

        binding.ivBack.setOnClickListener { findNavController().popBackStack() }
        binding.btnRetry.setOnClickListener { viewModel.loadDetail(symbol) }
        binding.btnHistoryRetry.setOnClickListener { viewModel.retryHistory() }
        binding.btnPerformanceRetry.setOnClickListener { viewModel.retryPerformance() }

        binding.tabOverview.setOnClickListener { viewModel.selectTab(EtfDetailTab.OVERVIEW) }
        binding.tabHistory.setOnClickListener { viewModel.selectTab(EtfDetailTab.HISTORY) }
        binding.tabPerformance.setOnClickListener { viewModel.selectTab(EtfDetailTab.PERFORMANCE) }

        binding.btnTf1m.setOnClickListener { viewModel.selectTimeframe("1M") }
        binding.btnTf3m.setOnClickListener { viewModel.selectTimeframe("3M") }
        binding.btnTf1y.setOnClickListener { viewModel.selectTimeframe("1Y") }

        observeState()
        viewModel.ensureLoaded(symbol)
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is EtfDetailUiState.Loading -> {
                            binding.layoutSkeleton.visibility = View.VISIBLE
                            binding.layoutHeaderBlock.visibility = View.GONE
                            binding.scrollContent.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                        }

                        is EtfDetailUiState.Success -> {
                            binding.layoutSkeleton.visibility = View.GONE
                            binding.layoutHeaderBlock.visibility = View.VISIBLE
                            binding.scrollContent.visibility = View.VISIBLE
                            binding.layoutError.visibility = View.GONE

                            renderHeader(state.etf)
                            renderTabSelection(state.selectedTab)
                            when (state.selectedTab) {
                                EtfDetailTab.OVERVIEW -> renderOverview(state.etf)
                                EtfDetailTab.HISTORY -> renderHistory(state.historyState, state.selectedTimeframe)
                                EtfDetailTab.PERFORMANCE -> renderPerformance(state.performanceState, state.etf)
                            }
                        }

                        is EtfDetailUiState.Error -> {
                            binding.layoutSkeleton.visibility = View.GONE
                            binding.layoutHeaderBlock.visibility = View.GONE
                            binding.scrollContent.visibility = View.GONE
                            binding.layoutError.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun renderHeader(etf: EtfItem) {
        binding.tvTopTitle.text = etf.symbol
        binding.tvEtfName.text = etf.name
        binding.tvEtfSymbol.text = etf.symbol
        binding.tvEtfShariah.visibility =
            if (etf.isShariahCompliant) View.VISIBLE else View.GONE
        binding.tvEtfPrice.text = FormatUtils.price(etf.currentPrice)

        val changeStr = etf.change?.let { String.format(Locale.US, "%+.2f", it) }
        val pctStr = etf.changePercent?.let { FormatUtils.percentSigned(it) }
        binding.tvEtfChange.text = when {
            changeStr != null && pctStr != null -> "$changeStr ($pctStr)"
            pctStr != null -> pctStr
            changeStr != null -> changeStr
            else -> FormatUtils.NA
        }
        val colorRes = when {
            etf.changePercent == null -> R.color.color_text_secondary
            etf.changePercent >= 0 -> R.color.color_positive
            else -> R.color.color_negative
        }
        binding.tvEtfChange.setTextColor(ContextCompat.getColor(requireContext(), colorRes))
    }

    private fun renderTabSelection(selected: EtfDetailTab) {
        applyPill(binding.tabOverview, selected == EtfDetailTab.OVERVIEW)
        applyPill(binding.tabHistory, selected == EtfDetailTab.HISTORY)
        applyPill(binding.tabPerformance, selected == EtfDetailTab.PERFORMANCE)

        binding.sectionOverview.visibility = if (selected == EtfDetailTab.OVERVIEW) View.VISIBLE else View.GONE
        binding.sectionHistory.visibility = if (selected == EtfDetailTab.HISTORY) View.VISIBLE else View.GONE
        binding.sectionPerformance.visibility = if (selected == EtfDetailTab.PERFORMANCE) View.VISIBLE else View.GONE
    }

    private fun applyPill(view: TextView, isSelected: Boolean) {
        if (isSelected) {
            view.setBackgroundResource(R.drawable.bg_pill_chart_toggle_selected)
            view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_primary))
        } else {
            view.background = null
            view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
        }
    }

    private fun renderOverview(etf: EtfItem) {
        if (etf.description.isNullOrBlank()) {
            binding.tvEtfDescription.visibility = View.GONE
        } else {
            binding.tvEtfDescription.visibility = View.VISIBLE
            binding.tvEtfDescription.text = etf.description
        }

        binding.layoutFundMetrics.removeAllViews()
        addRow(binding.layoutFundMetrics, "Fund Manager", etf.fundManager)
        addRow(binding.layoutFundMetrics, "Category", etf.category)
        addRow(binding.layoutFundMetrics, "Benchmark", etf.benchmarkIndex)
        addRow(binding.layoutFundMetrics, "Expense Ratio", etf.expenseRatio?.let { FormatUtils.percent(it) })
        addRow(binding.layoutFundMetrics, "Inception Date", etf.inceptionDate?.let { FormatUtils.dateFull(it) })
        addRow(binding.layoutFundMetrics, "Total Assets", FormatUtils.largeAmountPkr(etf.totalAssetsPkr))
        addRow(binding.layoutFundMetrics, "Shariah Compliant", if (etf.isShariahCompliant) "Yes" else "No")

        val quote = etf.quote
        if (quote == null) {
            binding.titleQuote.visibility = View.GONE
            binding.layoutQuoteMetrics.visibility = View.GONE
            binding.tvQuoteAsOf.visibility = View.GONE
        } else {
            binding.titleQuote.visibility = View.VISIBLE
            binding.layoutQuoteMetrics.visibility = View.VISIBLE
            binding.layoutQuoteMetrics.removeAllViews()
            addRow(binding.layoutQuoteMetrics, "Open", FormatUtils.price(quote.openPrice))
            addRow(binding.layoutQuoteMetrics, "High", FormatUtils.price(quote.highPrice))
            addRow(binding.layoutQuoteMetrics, "Low", FormatUtils.price(quote.lowPrice))
            addRow(binding.layoutQuoteMetrics, "Prev Close", FormatUtils.price(quote.closePrice))
            addRow(binding.layoutQuoteMetrics, "Volume", quote.volume?.let { FormatUtils.volume(it) })
            addRow(binding.layoutQuoteMetrics, "Bid", FormatUtils.price(quote.bidPrice))
            addRow(binding.layoutQuoteMetrics, "Ask", FormatUtils.price(quote.askPrice))

            val asOfParts = mutableListOf<String>()
            FormatUtils.parseDate(quote.dataAsOf)?.let { asOfParts.add("As of ${FormatUtils.dateFull(it)}") }
            if (!quote.quoteSource.isNullOrBlank()) asOfParts.add(quote.quoteSource)
            if (asOfParts.isEmpty()) {
                binding.tvQuoteAsOf.visibility = View.GONE
            } else {
                binding.tvQuoteAsOf.visibility = View.VISIBLE
                binding.tvQuoteAsOf.text = asOfParts.joinToString(" · ")
            }
        }
    }

    private fun renderHistory(historyState: EtfHistoryUiState, timeframe: String) {
        applyPill(binding.btnTf1m, timeframe == "1M")
        applyPill(binding.btnTf3m, timeframe == "3M")
        applyPill(binding.btnTf1y, timeframe == "1Y")

        when (historyState) {
            is EtfHistoryUiState.Loading -> {
                binding.progressHistory.visibility = View.VISIBLE
                binding.layoutOhlcvHeader.visibility = View.GONE
                binding.rvHistory.visibility = View.GONE
                binding.layoutHistoryMessage.visibility = View.GONE
            }

            is EtfHistoryUiState.Success -> {
                binding.progressHistory.visibility = View.GONE
                binding.layoutHistoryMessage.visibility = View.GONE
                binding.layoutOhlcvHeader.visibility = View.VISIBLE
                binding.rvHistory.visibility = View.VISIBLE
                historyAdapter.submitList(historyState.entries)
            }

            is EtfHistoryUiState.Empty -> {
                binding.progressHistory.visibility = View.GONE
                binding.layoutOhlcvHeader.visibility = View.GONE
                binding.rvHistory.visibility = View.GONE
                binding.layoutHistoryMessage.visibility = View.VISIBLE
                binding.tvHistoryMessage.text = "No price history for this period."
                binding.btnHistoryRetry.visibility = View.GONE
            }

            is EtfHistoryUiState.Error -> {
                binding.progressHistory.visibility = View.GONE
                binding.layoutOhlcvHeader.visibility = View.GONE
                binding.rvHistory.visibility = View.GONE
                binding.layoutHistoryMessage.visibility = View.VISIBLE
                binding.tvHistoryMessage.text = historyState.message
                binding.btnHistoryRetry.visibility = View.VISIBLE
            }
        }
    }

    private fun renderPerformance(performanceState: EtfPerformanceUiState, etf: EtfItem) {
        when (performanceState) {
            is EtfPerformanceUiState.Loading -> {
                binding.progressPerformance.visibility = View.VISIBLE
                binding.layoutPerfHeader.visibility = View.GONE
                binding.layoutPerformanceRows.visibility = View.GONE
                binding.layoutPerfMetrics.visibility = View.GONE
                binding.layoutPerformanceMessage.visibility = View.GONE
            }

            is EtfPerformanceUiState.Success -> {
                binding.progressPerformance.visibility = View.GONE
                binding.layoutPerformanceMessage.visibility = View.GONE
                bindPerformance(performanceState.performance, etf)
            }

            is EtfPerformanceUiState.Error -> {
                binding.progressPerformance.visibility = View.GONE
                binding.layoutPerfHeader.visibility = View.GONE
                binding.layoutPerformanceRows.visibility = View.GONE
                binding.layoutPerfMetrics.visibility = View.GONE
                binding.layoutPerformanceMessage.visibility = View.VISIBLE
                binding.tvPerformanceMessage.text = performanceState.message
            }
        }
    }

    private fun bindPerformance(perf: EtfPerformance, etf: EtfItem) {
        if (perf.benchmarkIndex.isNullOrBlank()) {
            binding.tvPerfBenchmark.visibility = View.GONE
        } else {
            binding.tvPerfBenchmark.visibility = View.VISIBLE
            binding.tvPerfBenchmark.text = "Benchmark: ${perf.benchmarkIndex}"
        }

        binding.layoutPerfHeader.visibility = View.VISIBLE
        binding.tvPerfColEtf.text = etf.symbol
        binding.layoutPerformanceRows.visibility = View.VISIBLE
        binding.layoutPerformanceRows.removeAllViews()

        val r = perf.returns
        val b = perf.benchmarkReturns
        val periods = listOf(
            "1D" to (r?.oneDay to b?.oneDay),
            "1W" to (r?.oneWeek to b?.oneWeek),
            "1M" to (r?.oneMonth to b?.oneMonth),
            "3M" to (r?.threeMonths to b?.threeMonths),
            "1Y" to (r?.oneYear to b?.oneYear),
            "YTD" to (r?.ytd to b?.ytd)
        )
        periods.forEach { (label, values) ->
            val (etfVal, benchVal) = values
            if (etfVal == null && benchVal == null) return@forEach
            addPerformanceRow(label, etfVal, benchVal)
        }

        binding.layoutPerfMetrics.visibility = View.VISIBLE
        binding.layoutPerfMetrics.removeAllViews()
        addRow(binding.layoutPerfMetrics, "Tracking Difference (1M)", FormatUtils.percentSigned(perf.trackingDifference1m))
        addRow(binding.layoutPerfMetrics, "Volatility (Annualized)", FormatUtils.percent(perf.volatilityAnnualized))
    }

    private fun addPerformanceRow(period: String, etfVal: Double?, benchVal: Double?) {
        val row = ItemEtfPerformanceRowBinding.inflate(layoutInflater, binding.layoutPerformanceRows, false)
        row.tvRowPeriod.text = period
        row.tvRowEtf.text = FormatUtils.percentSigned(etfVal)
        row.tvRowEtf.setTextColor(ContextCompat.getColor(requireContext(), returnColor(etfVal)))
        row.tvRowBenchmark.text = FormatUtils.percentSigned(benchVal)
        row.tvRowBenchmark.setTextColor(ContextCompat.getColor(requireContext(), returnColor(benchVal)))
        binding.layoutPerformanceRows.addView(row.root)
    }

    private fun returnColor(value: Double?): Int = when {
        value == null -> R.color.color_text_secondary
        value >= 0 -> R.color.color_positive
        else -> R.color.color_negative
    }

    private fun addRow(container: LinearLayout, label: String, value: String?) {
        if (value.isNullOrBlank() || value == FormatUtils.NA) return
        val row = ItemDetailLabelValueBinding.inflate(layoutInflater, container, false)
        row.tvLabel.text = label
        row.tvValue.text = value
        container.addView(row.root)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
