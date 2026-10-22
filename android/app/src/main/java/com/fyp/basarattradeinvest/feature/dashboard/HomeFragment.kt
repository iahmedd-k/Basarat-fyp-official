package com.fyp.basarattradeinvest.feature.dashboard

import android.content.res.ColorStateList
import android.graphics.DashPathEffect
import android.graphics.drawable.GradientDrawable
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
import com.fyp.basarattradeinvest.databinding.FragmentHomeBinding
import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistItem
import com.fyp.basarattradeinvest.feature.news.adapter.NewsArticleAdapter
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.formatter.ValueFormatter
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

class HomeFragment : Fragment() {

    private var _binding: FragmentHomeBinding? = null
    private val binding get() = _binding!!

    private val viewModel: HomeViewModel by activityViewModels()

    private val priceFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    private val indexFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    private val trendSessionFormat = SimpleDateFormat("d MMM", Locale.US)

    private val newsArticleAdapter by lazy {
        NewsArticleAdapter { article ->
            val bundle = Bundle().apply { putString("articleId", article.id) }
            findNavController().navigate(R.id.newsArticleDetailFragment, bundle)
        }
    }
    private var lastBoundSuccess: HomeUiState.Success? = null
    private var hasPlottedTrend = false

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentHomeBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerViews()
        setupListeners()
        setupBenchmarkChart()
        observeUiState()
        viewModel.ensureLoaded()
    }

    private fun setupRecyclerViews() {
        binding.rvMarketNews.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = newsArticleAdapter
            isNestedScrollingEnabled = false
        }
    }

    private fun setupListeners() {
        binding.swipeRefresh.setOnRefreshListener {
            viewModel.refresh()
        }

        binding.btnRetryHome.setOnClickListener {
            viewModel.refresh()
        }

        binding.btnRetryWatchlist.setOnClickListener {
            viewModel.retryWatchlist()
        }

        binding.btnExploreMarkets.setOnClickListener {
            findNavController().navigate(R.id.nav_markets)
        }

        // 1. Search Bar -> Stock Search
        binding.btnSearchBar.setOnClickListener {
            findNavController().navigate(R.id.action_home_to_stockSearch)
        }

        // 2. Header Actions
        binding.btnAlerts.setOnClickListener {
            findNavController().navigate(R.id.alertsFragment)
        }

        binding.btnProfile.setOnClickListener {
            findNavController().navigate(R.id.editProfileFragment)
        }

        binding.btnMenu.setOnClickListener {
            (requireActivity() as? com.fyp.basarattradeinvest.MainActivity)?.openDrawer()
        }

        // 3. Watchlist "View All"
        binding.btnViewWatchlist.setOnClickListener {
            findNavController().navigate(R.id.action_home_to_watchlist)
        }

        // 4. News "View All" -> News & Events
        binding.btnViewMarketNews.setOnClickListener {
            findNavController().navigate(R.id.newsEventsFragment)
        }

        // 5. Timeframe Selector Pills for Benchmark
        binding.tabTimeframe1d.setOnClickListener { viewModel.selectTimeframe("1D") }
        binding.tabTimeframe1w.setOnClickListener { viewModel.selectTimeframe("1W") }
        binding.tabTimeframe1m.setOnClickListener { viewModel.selectTimeframe("1M") }
        binding.tabTimeframe3m.setOnClickListener { viewModel.selectTimeframe("3M") }
    }

    private fun setupBenchmarkChart() {
        val axisColor = ContextCompat.getColor(requireContext(), R.color.color_text_tertiary)
        binding.chartMarketTrend.apply {
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(false)
            isDragEnabled = false
            setScaleEnabled(false)
            setPinchZoom(false)
            setDrawGridBackground(false)
            setNoDataText("")
            // Gridlines mirror the reference chart: dashed horizontals only, no frame lines.
            axisLeft.apply {
                isEnabled = true
                setDrawAxisLine(false)
                setDrawGridLines(true)
                gridColor = axisColor
                gridLineWidth = 0.8f
                setGridDashedLine(DashPathEffect(floatArrayOf(6f, 6f), 0f))
                textColor = axisColor
                textSize = 9f
                setLabelCount(4, false)
                valueFormatter = object : ValueFormatter() {
                    override fun getFormattedValue(value: Float): String =
                        String.format(Locale.US, "%+.1f%%", value)
                }
            }
            axisRight.isEnabled = false
            xAxis.apply {
                isEnabled = true
                position = XAxis.XAxisPosition.BOTTOM
                setDrawAxisLine(false)
                setDrawGridLines(false)
                textColor = axisColor
                textSize = 9f
                setLabelCount(5, false)
                // Ticks may only land on whole sessions, otherwise a short window renders the
                // same date twice at neighbouring fractional positions.
                granularity = 1f
            }
            setExtraOffsets(2f, 8f, 4f, 0f)
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is HomeUiState.Loading -> {
                            lastBoundSuccess = null
                            binding.layoutHomeSkeleton.visibility = View.VISIBLE
                            binding.layoutHomeError.visibility = View.GONE
                            binding.scrollContent.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false
                        }
                        is HomeUiState.Error -> {
                            lastBoundSuccess = null
                            binding.layoutHomeSkeleton.visibility = View.GONE
                            binding.layoutHomeError.visibility = View.VISIBLE
                            binding.scrollContent.visibility = View.GONE
                            binding.tvHomeErrorMsg.text = state.message
                            binding.swipeRefresh.isRefreshing = false
                        }
                        is HomeUiState.Success -> {
                            binding.layoutHomeSkeleton.visibility = View.GONE
                            binding.layoutHomeError.visibility = View.GONE
                            binding.scrollContent.visibility = View.VISIBLE
                            binding.swipeRefresh.isRefreshing = false
                            bindSuccessState(state)
                        }
                    }
                }
            }
        }
    }

    override fun onStart() {
        super.onStart()
        viewModel.setLiveUpdatesActive(true)
    }

    override fun onStop() {
        viewModel.setLiveUpdatesActive(false)
        super.onStop()
    }

    private fun bindSuccessState(state: HomeUiState.Success) {
        val previous = lastBoundSuccess
        val context = requireContext()

        // 1. Header Greeting & User Name
        if (previous == null || previous.userName != state.userName) {
            val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
            val greetingPrefix = when (hour) {
                in 4..11 -> "Good morning,"
                in 12..16 -> "Good afternoon,"
                in 17..22 -> "Good evening,"
                else -> "Welcome back,"
            }
            binding.tvGreeting.text = greetingPrefix
            binding.tvUserName.text = state.userName
        }

        // Market Status
        if (previous == null || previous.marketStatus != state.marketStatus || previous.isMarketOpen != state.isMarketOpen) {
            binding.layoutMarketStatus.visibility = if (state.marketStatus == null) View.GONE else View.VISIBLE
            binding.tvMarketStatus.text = state.marketStatus
            val statusColor = if (state.isMarketOpen) {
                ContextCompat.getColor(context, R.color.color_positive)
            } else {
                ContextCompat.getColor(context, R.color.color_neutral)
            }
            binding.dotMarketStatus.backgroundTintList = ColorStateList.valueOf(statusColor)
            // The benchmark card's corner chip mirrors the same live session state.
            binding.tvBenchmarkStatusChip.visibility =
                if (state.marketStatus == null) View.GONE else View.VISIBLE
            binding.tvBenchmarkStatusChip.text = state.marketStatus
            binding.tvBenchmarkStatusChip.setTextColor(statusColor)
        }

        // Notification Badge
        if (previous == null || previous.activeAlertsCount != state.activeAlertsCount) {
            if (state.activeAlertsCount > 0) {
                binding.tvAlertBadge.visibility = View.VISIBLE
                binding.tvAlertBadge.text = if (state.activeAlertsCount > 9) "9+" else state.activeAlertsCount.toString()
            } else {
                binding.tvAlertBadge.visibility = View.GONE
            }
        }

        // 2. Market Pulse Indices
        if (previous == null || previous.marketIndices != state.marketIndices) {
            bindMarketPulse(state.marketIndices)
        }

        // 3. Benchmark Trend Card (KSE-100)
        if (previous == null || previous.selectedBenchmarkIndex != state.selectedBenchmarkIndex || previous.selectedTimeframe != state.selectedTimeframe) {
            bindBenchmarkCard(state)
        }
        if (previous == null || previous.benchmarkTrend != state.benchmarkTrend) {
            bindBenchmarkTrend(state.benchmarkTrend)
        }

        // 4. Market Overview + Sentiment (moved from the Markets screen)
        if (previous == null || previous.sentiment != state.sentiment) {
            bindBreadth(state.sentiment)
            bindSentiment(state.sentiment)
        }

        // 5. Watchlist Preview
        if (previous == null || previous.watchlist != state.watchlist) {
            bindWatchlist(state.watchlist)
        }

        // 6. Market News
        if (previous == null || previous.recentNews != state.recentNews) {
            newsArticleAdapter.submitList(state.recentNews)
        }
        lastBoundSuccess = state
    }

    private fun bindMarketPulse(indices: List<MarketIndex>) {
        val context = requireContext()

        // Index 1 (KSE-100)
        val kse100 = indices.firstOrNull { it.code.contains("100") || it.name.contains("100") } ?: indices.getOrNull(0)
        kse100?.let {
            binding.tvIndexName1.text = it.name
            binding.tvIndexVal1.text = indexFormat.format(it.currentPoints)
            val isPos = it.changePercent >= 0
            val prefix = if (isPos) "+" else ""
            binding.tvIndexChange1.text = String.format(Locale.US, "%s%.2f%%", prefix, it.changePercent)
            val col = ContextCompat.getColor(context, if (isPos) R.color.color_positive else R.color.color_negative)
            binding.tvIndexChange1.setTextColor(col)
        }

        // Index 2 (KSE-30)
        val kse30 = indices.firstOrNull { it.code.contains("30") && !it.code.contains("KMI") } ?: indices.getOrNull(1)
        kse30?.let {
            binding.tvIndexName2.text = it.name
            binding.tvIndexVal2.text = indexFormat.format(it.currentPoints)
            val isPos = it.changePercent >= 0
            val prefix = if (isPos) "+" else ""
            binding.tvIndexChange2.text = String.format(Locale.US, "%s%.2f%%", prefix, it.changePercent)
            val col = ContextCompat.getColor(context, if (isPos) R.color.color_positive else R.color.color_negative)
            binding.tvIndexChange2.setTextColor(col)
        }

        // Index 3 (KMI-30)
        val kmi30 = indices.firstOrNull { it.code.contains("KMI") || it.name.contains("KMI") } ?: indices.getOrNull(2)
        kmi30?.let {
            binding.tvIndexName3.text = it.name
            binding.tvIndexVal3.text = indexFormat.format(it.currentPoints)
            val isPos = it.changePercent >= 0
            val prefix = if (isPos) "+" else ""
            binding.tvIndexChange3.text = String.format(Locale.US, "%s%.2f%%", prefix, it.changePercent)
            val col = ContextCompat.getColor(context, if (isPos) R.color.color_positive else R.color.color_negative)
            binding.tvIndexChange3.setTextColor(col)
        }

        // Index 4 (ALLSHR)
        val allshr = indices.firstOrNull { it.code.contains("ALL", ignoreCase = true) } ?: indices.getOrNull(3)
        allshr?.let {
            binding.tvIndexName4.text = it.name
            binding.tvIndexVal4.text = indexFormat.format(it.currentPoints)
            val isPos = it.changePercent >= 0
            val prefix = if (isPos) "+" else ""
            binding.tvIndexChange4.text = String.format(Locale.US, "%s%.2f%%", prefix, it.changePercent)
            val col = ContextCompat.getColor(context, if (isPos) R.color.color_positive else R.color.color_negative)
            binding.tvIndexChange4.setTextColor(col)
        }
    }

    private fun bindBenchmarkCard(state: HomeUiState.Success) {
        val benchmark = state.selectedBenchmarkIndex
        val context = requireContext()

        if (benchmark != null) {
            binding.tvBenchmarkTitle.text = benchmark.name
            binding.tvBenchmarkPoints.text = indexFormat.format(benchmark.currentPoints)

            val isPos = benchmark.changePercent >= 0
            val prefix = if (isPos) "+" else ""
            val changePtsStr = String.format(Locale.US, "%s%.2f", prefix, benchmark.changePoints)
            val changePctStr = String.format(Locale.US, "%s%.2f%%", prefix, benchmark.changePercent)
            binding.tvBenchmarkChange.text = "$changePtsStr ($changePctStr)"

            val trendColor = ContextCompat.getColor(
                context,
                if (isPos) R.color.color_positive else R.color.color_negative
            )
            binding.tvBenchmarkChange.setTextColor(trendColor)
            binding.ivBenchmarkArrow.setImageResource(
                if (isPos) R.drawable.ic_trend_up else R.drawable.ic_trend_down
            )
            binding.ivBenchmarkArrow.imageTintList = ColorStateList.valueOf(trendColor)

            if (benchmark.high > 0.0) {
                binding.tvBenchmarkHigh.text = "Day High: ${indexFormat.format(benchmark.high)}"
            } else {
                binding.tvBenchmarkHigh.text = "Day High: --"
            }

            if (benchmark.low > 0.0) {
                binding.tvBenchmarkLow.text = "Day Low: ${indexFormat.format(benchmark.low)}"
            } else {
                binding.tvBenchmarkLow.text = "Day Low: --"
            }
        }

        // Timeframe selector styles
        val pills = listOf(
            binding.tabTimeframe1d to "1D",
            binding.tabTimeframe1w to "1W",
            binding.tabTimeframe1m to "1M",
            binding.tabTimeframe3m to "3M"
        )
        pills.forEach { (view, tf) ->
            if (tf == state.selectedTimeframe) {
                view.setBackgroundResource(R.drawable.bg_pill_range_selected)
                view.setTextColor(ContextCompat.getColor(context, R.color.color_surface))
            } else {
                view.setBackgroundResource(R.drawable.bg_timeframe_chip_unselected)
                view.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
            }
        }
    }

    /**
     * Plots the derived benchmark trend. No index-history endpoint exists, so this line is an
     * equal-weight proxy of the constituents and the caption carries that provenance instead of
     * letting it read as the official index path.
     */
    private fun bindBenchmarkTrend(trendState: BenchmarkTrendUiState) {
        val trend = (trendState as? BenchmarkTrendUiState.Success)?.trend
        if (trend == null || trend.points.size < 2) {
            // A build in flight keeps the line already on screen; a pill with nothing to plot
            // collapses the chart instead of borrowing the previous pill's line.
            if (trendState == BenchmarkTrendUiState.Loading && hasPlottedTrend) return
            hasPlottedTrend = false
            binding.chartMarketTrend.clear()
            binding.chartMarketTrend.visibility = View.GONE
            binding.tvBenchmarkTrendCaption.visibility = View.GONE
            return
        }
        hasPlottedTrend = true
        binding.chartMarketTrend.visibility = View.VISIBLE

        val isUp = trend.points.last().changePct >= 0f
        val trendColor = ContextCompat.getColor(
            requireContext(),
            if (isUp) R.color.color_positive else R.color.color_negative
        )
        val dataSet = LineDataSet(
            trend.points.mapIndexed { idx, point -> Entry(idx.toFloat(), point.changePct) },
            "Benchmark"
        ).apply {
            color = trendColor
            lineWidth = 2f
            setDrawCircles(false)
            setDrawValues(false)
            mode = LineDataSet.Mode.CUBIC_BEZIER
            setDrawFilled(true)
            fillDrawable = GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(trendColor and 0x00FFFFFF or 0x40000000, trendColor and 0x00FFFFFF)
            )
        }
        // Ticks land on fractional indices for short windows, so round to the nearest session —
        // every label is a real trading date at (approximately) that x position.
        val sessionLabels = trend.points.map { trendSessionFormat.format(Date(it.timestamp)) }
        binding.chartMarketTrend.xAxis.valueFormatter = object : ValueFormatter() {
            override fun getFormattedValue(value: Float): String {
                val index = value.roundToInt()
                return if (index in sessionLabels.indices) sessionLabels[index] else ""
            }
        }
        binding.chartMarketTrend.data = LineData(dataSet)
        binding.chartMarketTrend.invalidate()

        binding.tvBenchmarkTrendCaption.text = getString(
            R.string.benchmark_trend_caption,
            trend.stockCount,
            trendSessionFormat.format(Date(trend.firstSessionTimestamp)),
            trendSessionFormat.format(Date(trend.lastSessionTimestamp))
        )
        binding.tvBenchmarkTrendCaption.visibility = View.VISIBLE
    }

    private fun bindWatchlist(state: WatchlistUiState) {
        binding.layoutWatchlistLoading.visibility = View.GONE
        binding.layoutWatchlistEmpty.visibility = View.GONE
        binding.layoutWatchlistError.visibility = View.GONE
        binding.layoutWatchlistItems.visibility = View.GONE

        when (state) {
            WatchlistUiState.Loading -> {
                binding.layoutWatchlistLoading.visibility = View.VISIBLE
                return
            }
            WatchlistUiState.Empty -> {
                binding.layoutWatchlistEmpty.visibility = View.VISIBLE
                return
            }
            is WatchlistUiState.Error -> {
                binding.tvWatchlistError.text = state.message
                binding.layoutWatchlistError.visibility = View.VISIBLE
                return
            }
            is WatchlistUiState.Success -> Unit
        }
        val stocks = (state as WatchlistUiState.Success).watchlist.items
        binding.layoutWatchlistItems.visibility = View.VISIBLE

        val s1 = stocks.getOrNull(0)
        if (s1 != null) {
            bindWatchlistCard(s1, 1)
        } else {
            binding.cardWatchlistItem1.visibility = View.GONE
        }

        val s2 = stocks.getOrNull(1)
        if (s2 != null) {
            bindWatchlistCard(s2, 2)
        } else {
            binding.cardWatchlistItem2.visibility = View.GONE
        }
    }

    private fun bindWatchlistCard(stock: WatchlistItem, position: Int) {
        val card: View
        val symbol: TextView
        val name: TextView
        val price: TextView
        val change: TextView
        val sparkline: com.fyp.basarattradeinvest.core.ui.components.MiniSparklineView
        if (position == 1) {
            card = binding.cardWatchlistItem1
            symbol = binding.tvWatchlistSym1
            name = binding.tvWatchlistName1
            price = binding.tvWatchlistPrice1
            change = binding.tvWatchlistChange1
            sparkline = binding.sparklineWatchlist1
        } else {
            card = binding.cardWatchlistItem2
            symbol = binding.tvWatchlistSym2
            name = binding.tvWatchlistName2
            price = binding.tvWatchlistPrice2
            change = binding.tvWatchlistChange2
            sparkline = binding.sparklineWatchlist2
        }

        card.visibility = View.VISIBLE
        symbol.text = stock.symbol
        name.text = stock.name?.takeIf { it.isNotBlank() } ?: stock.symbol
        price.text = stock.currentPrice?.let(priceFormat::format) ?: "—"

        val changePercent = stock.changePercent
        // Prefer the real change + sparkline whenever we have a change value, even if the
        // quote is flagged stale (PSX feed is end-of-day/delayed). Only fall back to the
        // "Delayed" label when there is no change data at all to graph.
        if (changePercent != null) {
            val isPos = changePercent >= 0
            val prefix = if (isPos) "+" else ""
            change.text = String.format(Locale.US, "%s%.2f%%", prefix, changePercent)
            val color = ContextCompat.getColor(
                requireContext(),
                if (isPos) R.color.color_positive else R.color.color_negative
            )
            change.setTextColor(color)
            sparkline.setTrend(isPos)
            sparkline.visibility = View.VISIBLE
        } else if (stock.isStale) {
            change.text = "Delayed"
            change.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_tertiary))
            sparkline.visibility = View.INVISIBLE
        } else {
            change.text = "—"
            change.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_tertiary))
            sparkline.visibility = View.INVISIBLE
        }

        card.setOnClickListener {
            val bundle = Bundle().apply { putString("symbol", stock.symbol) }
            findNavController().navigate(R.id.stockDetailFragment, bundle)
        }
    }

    /**
     * Advance/decline breadth. Both moved cards stay hidden until /market/sentiment-overview
     * answers rather than painting an empty bar that reads as a flat market.
     */
    private fun bindBreadth(sentiment: MarketSentiment?) {
        if (sentiment == null) {
            binding.layoutMarketOverview.visibility = View.GONE
            return
        }
        binding.layoutMarketOverview.visibility = View.VISIBLE

        val total = sentiment.advancing + sentiment.declining + sentiment.unchanged
        binding.tvTotalStocks.text = if (total > 0) "Total $total \u203A" else "Total -- \u203A"
        binding.tvOverviewValue.text = if (total > 0)
            String.format(Locale.US, "%.2fx", sentiment.advanceDeclineRatio) else "--"
        binding.tvOverviewVolume.text = sentiment.advancing.toString()
        binding.tvOverviewTrades.text = sentiment.declining.toString()

        // Raw counts as weights: a zero total collapses the bar instead of leaving the XML's
        // equal-thirds default, which would read as a balanced market.
        (binding.barUp.layoutParams as LinearLayout.LayoutParams).weight =
            sentiment.advancing.toFloat()
        (binding.barUnchanged.layoutParams as LinearLayout.LayoutParams).weight =
            sentiment.unchanged.toFloat()
        (binding.barDown.layoutParams as LinearLayout.LayoutParams).weight =
            sentiment.declining.toFloat()
        binding.barUp.requestLayout()

        binding.tvUpCount.text = "\u25B2 Up ${sentiment.advancing}"
        binding.tvUnchangedCount.text = "Unchanged ${sentiment.unchanged}"
        binding.tvDownCount.text = "\u25BC Down ${sentiment.declining}"
    }

    private fun bindSentiment(sentiment: MarketSentiment?) {
        if (sentiment == null) {
            binding.cardMarketSentiment.visibility = View.GONE
            return
        }
        binding.cardMarketSentiment.visibility = View.VISIBLE

        binding.tvSentimentScore.text = "${sentiment.overallScore} / 100"
        binding.tvSentimentLabel.text = sentiment.sentimentLabel

        val isBullish = sentiment.sentimentLabel.contains("Bull", ignoreCase = true)
        val isBearish = sentiment.sentimentLabel.contains("Bear", ignoreCase = true)
        val labelColor = when {
            isBullish -> R.color.color_positive
            isBearish -> R.color.color_negative
            else -> R.color.color_neutral
        }
        binding.tvSentimentLabel.setTextColor(ContextCompat.getColor(requireContext(), labelColor))

        // Percentages as weights so the three segments split the track by their real share; a
        // zero total collapses the bar rather than leaving the XML's equal-thirds default.
        (binding.barSentimentPositive.layoutParams as LinearLayout.LayoutParams).weight =
            sentiment.positivePercent.toFloat()
        (binding.barSentimentNeutral.layoutParams as LinearLayout.LayoutParams).weight =
            sentiment.neutralPercent.toFloat()
        (binding.barSentimentNegative.layoutParams as LinearLayout.LayoutParams).weight =
            sentiment.negativePercent.toFloat()
        binding.barSentimentPositive.requestLayout()

        binding.tvSentimentPos.text = "Pos ${sentiment.positivePercent}%"
        binding.tvSentimentNeu.text = "Neu ${sentiment.neutralPercent}%"
        binding.tvSentimentNeg.text = "Neg ${sentiment.negativePercent}%"
    }

    override fun onDestroyView() {
        super.onDestroyView()
        lastBoundSuccess = null
        hasPlottedTrend = false
        _binding = null
    }
}
