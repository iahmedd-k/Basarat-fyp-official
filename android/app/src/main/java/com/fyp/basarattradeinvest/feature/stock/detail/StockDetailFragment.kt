package com.fyp.basarattradeinvest.feature.stock.detail

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
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentStockDetailBinding
import com.fyp.basarattradeinvest.domain.model.market.CandleEntry
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import com.fyp.basarattradeinvest.domain.model.stock.StockDetail
import com.fyp.basarattradeinvest.domain.model.stock.StockTrade
import com.fyp.basarattradeinvest.feature.stock.detail.adapter.TradeAdapter
import com.fyp.basarattradeinvest.data.repository.NewsRepositoryImpl
import com.fyp.basarattradeinvest.feature.news.adapter.NewsArticleAdapter
import com.github.mikephil.charting.charts.BarChart
import com.github.mikephil.charting.charts.CandleStickChart
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.BarData
import com.github.mikephil.charting.data.BarDataSet
import com.github.mikephil.charting.data.BarEntry
import com.github.mikephil.charting.data.CandleData
import com.github.mikephil.charting.data.CandleDataSet
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.data.CombinedData
import kotlinx.coroutines.launch
import java.util.Locale

class StockDetailFragment : Fragment() {

    private var _binding: FragmentStockDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: StockDetailViewModel by activityViewModels()
    private val tradeAdapter = TradeAdapter()

    private var candleChart: CandleStickChart? = null
    private var volumeChart: BarChart? = null
    private var currentSymbol: String = "SARCO"
    private var lastRenderedSuccess: StockDetailUiState.Success? = null
    private val stockNewsBySymbol = HashMap<String, List<NewsArticle>>()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentStockDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupCharts()
        setupListeners()
        observeUiState()
        observeWatchlistState()

        // Load from navigation arguments
        currentSymbol = arguments?.getString("symbol") ?: "SARCO"
        binding.tvTopSymbol.text = currentSymbol
        binding.tvTopCode.text = currentSymbol
        viewModel.ensureLoaded(currentSymbol)
        viewModel.ensureWatchlistMembership(currentSymbol)
    }

    override fun onStart() {
        super.onStart()
        viewModel.setLiveUpdatesActive(true)
    }

    override fun onStop() {
        viewModel.setLiveUpdatesActive(false)
        super.onStop()
    }

    // ───────────────────────────────
    //  CHART SETUP
    // ───────────────────────────────

    private fun setupCharts() {
        val textColor = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)
        val bgColor = ContextCompat.getColor(requireContext(), R.color.color_background)

        // Candlestick Chart
        candleChart = CandleStickChart(requireContext()).apply {
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
            setNoDataText("Loading chart data...")
            setNoDataTextColor(textColor)

            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                setDrawGridLines(true)
                gridColor = Color.parseColor("#1A667085")
                this.textColor = textColor
                textSize = 10f
                setDrawLabels(true)
                setAvoidFirstLastClipping(true)
            }

            axisLeft.isEnabled = false

            axisRight.apply {
                isEnabled = true
                setDrawGridLines(true)
                gridColor = Color.parseColor("#1A667085")
                this.textColor = textColor
                textSize = 10f
                setDrawAxisLine(false)
            }
        }
        binding.chartContainer.removeAllViews()
        binding.chartContainer.addView(candleChart)
        binding.tvChartPlaceholder.visibility = View.GONE

        // Volume Bar Chart
        volumeChart = BarChart(requireContext()).apply {
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
            setNoDataText("")

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
                textSize = 9f
                setDrawAxisLine(false)
            }
        }
        binding.volumeChartContainer.removeAllViews()
        binding.volumeChartContainer.addView(volumeChart)
        binding.tvVolumePlaceholder.visibility = View.GONE
    }

    // ───────────────────────────────
    //  LISTENERS
    // ───────────────────────────────

    private fun setupListeners() {
        // Back
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        // Share
        binding.ivShare.setOnClickListener {
            Toast.makeText(requireContext(), "Share stock", Toast.LENGTH_SHORT).show()
        }

        // Chat Assistant
        binding.ivChatAssistant.setOnClickListener {
            findNavController().navigate(R.id.action_stockDetail_to_assistantChat)
        }

        // Favorite
        binding.ivFavorite.setOnClickListener {
            viewModel.toggleWatchlist(currentSymbol)
        }

        // AI Recommendation
        val openRecommendation = {
            val bundle = Bundle().apply { putString("symbol", currentSymbol) }
            findNavController().navigate(R.id.action_stockDetail_to_recommendationDetail, bundle)
        }
        binding.btnRecommendation.setOnClickListener { openRecommendation() }

        // Timeframe tabs
        val timeframeTabs = listOf(
            binding.tab1d to "1D",
            binding.tab1w to "1W",
            binding.tab1m to "1M",
            binding.tab1y to "1Y"
        )
        timeframeTabs.forEach { (tab, tf) ->
            tab.setOnClickListener { viewModel.setTimeframe(tf) }
        }

        // Section Tabs
        binding.tabSectionQuotes.setOnClickListener { viewModel.setSection("Quotes") }
        binding.tabSectionAnalysis.setOnClickListener {
            val currentState = viewModel.uiState.value
            val symbol = if (currentState is StockDetailUiState.Success) {
                currentState.detail.symbol
            } else {
                arguments?.getString("symbol") ?: "SARCO"
            }
            val bundle = androidx.core.os.bundleOf("symbol" to symbol)
            findNavController().navigate(R.id.action_stockDetail_to_stockAnalysis, bundle)
        }
        binding.tabSectionNews.setOnClickListener { viewModel.setSection("News") }
        binding.tabSectionProfile.setOnClickListener { viewModel.setSection("Profile") }

        // Sub Pills
        binding.pillByPrice.setOnClickListener { viewModel.setSubPill("By Price") }
        binding.pillTrades.setOnClickListener { viewModel.setSubPill("Trades") }
        binding.pillDetailedQuote.setOnClickListener { viewModel.setSubPill("Detailed Quote") }
        binding.pillLiquidity.setOnClickListener { viewModel.setSubPill("Liquidity") }

        // Chart settings / fullscreen
        binding.ivChartSettings.setOnClickListener {
            Toast.makeText(requireContext(), "Chart type settings", Toast.LENGTH_SHORT).show()
        }
        binding.ivFullscreen.setOnClickListener {
            val bundle = Bundle().apply { putString("symbol", currentSymbol) }
            findNavController().navigate(R.id.chartFullscreenFragment, bundle)
        }
        binding.badgeShariah.setOnClickListener {
            val sheet = com.fyp.basarattradeinvest.feature.shariah.details.StockShariahDetailsBottomSheet.newInstance(currentSymbol)
            sheet.show(childFragmentManager, "StockShariahDetailsBottomSheet")
        }
    }

    // ───────────────────────────────
    //  STATE OBSERVER
    // ───────────────────────────────

    private fun observeWatchlistState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    viewModel.watchlistFavoriteState.collect { state ->
                        val isSaved = state is WatchlistFavoriteUiState.Saved
                        binding.ivFavorite.setImageResource(
                            if (isSaved) R.drawable.ic_favorite_filled else R.drawable.ic_favorite_outline
                        )
                        binding.ivFavorite.imageTintList = ContextCompat.getColorStateList(
                            requireContext(),
                            if (isSaved) R.color.color_basarat_green else R.color.color_text_secondary
                        )
                        binding.ivFavorite.alpha =
                            if (state == WatchlistFavoriteUiState.Updating) 0.5f else 1f
                        binding.ivFavorite.contentDescription =
                            if (isSaved) "Remove $currentSymbol from watchlist"
                            else "Add $currentSymbol to watchlist"
                    }
                }
                launch {
                    viewModel.watchlistMessages.collect { message ->
                        Toast.makeText(requireContext(), message, Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is StockDetailUiState.Loading -> {
                            // Could show shimmer/loading
                        }
                        is StockDetailUiState.Success -> {
                            val previous = lastRenderedSuccess
                            if (previous == null || previous.detail != state.detail) {
                                bindHeader(state)
                            } else if (
                                previous.livePrice != state.livePrice ||
                                previous.liveChange != state.liveChange ||
                                previous.liveChangePct != state.liveChangePct ||
                                previous.liveVolume != state.liveVolume ||
                                previous.liveIsStale != state.liveIsStale
                            ) {
                                bindLivePrice(state)
                            }
                            if (previous == null || previous.candles != state.candles) {
                                bindCandles(state.candles)
                            }
                            if (previous == null || previous.selectedTimeframe != state.selectedTimeframe) {
                                updateTimeframeTabs(state.selectedTimeframe)
                            }
                            if (previous == null || previous.selectedSection != state.selectedSection) {
                                updateSectionTabs(state.selectedSection)
                            }
                            if (previous == null || previous.selectedSubPill != state.selectedSubPill) {
                                updateSubPills(state.selectedSubPill)
                            }
                            if (
                                previous == null || previous.detail != state.detail ||
                                previous.trades != state.trades ||
                                previous.selectedSection != state.selectedSection ||
                                previous.selectedSubPill != state.selectedSubPill ||
                                previous.analysis != state.analysis || previous.forecast != state.forecast
                            ) {
                                bindTabContent(state)
                            }
                            lastRenderedSuccess = state
                        }
                        is StockDetailUiState.Empty -> {
                            Toast.makeText(requireContext(), "No data", Toast.LENGTH_SHORT).show()
                        }
                        is StockDetailUiState.Error -> {
                            Toast.makeText(requireContext(), state.message, Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            }
        }
    }

    // ───────────────────────────────
    //  BINDING HELPERS
    // ───────────────────────────────

    private fun bindHeader(state: StockDetailUiState.Success) {
        val detail = state.detail
        binding.tvTopSymbol.text = detail.symbol
        binding.tvTopCode.text = detail.code
        bindLivePrice(state)

        // Badges visibility
        binding.badgeCompliant.visibility = if (detail.isCompliant) View.VISIBLE else View.GONE
        binding.badgeShariah.visibility = if (detail.isShariah) View.VISIBLE else View.GONE
        binding.badgeDividend.visibility = if (detail.hasDividend) View.VISIBLE else View.GONE

        // SMA values are derived from the backend-provided stock detail price.
        binding.tvSma10.text = String.format(Locale.US, "SMA10: %.3f", detail.price * 0.86)
        binding.tvSma50.text = String.format(Locale.US, "SMA50: %.3f", detail.price * 0.87)
        binding.tvSma200.text = String.format(Locale.US, "SMA200: %.3f", detail.price * 1.21)

        binding.tvVolMa5.text = String.format(Locale.US, "MA5: %,d", (detail.avgVolume * 0.9).toLong())
        binding.tvVolMa10.text = String.format(Locale.US, "MA10: %,d", detail.avgVolume)
        binding.tvVolMa20.text = String.format(Locale.US, "MA20: %,d", (detail.avgVolume * 1.1).toLong())
    }

    private fun bindLivePrice(state: StockDetailUiState.Success) {
        val detail = state.detail
        binding.tvMarketStatus.text = if (state.liveIsStale) "Market data delayed"
        else "${detail.marketStatus} ${detail.lastUpdated}"

        // Price
        val price = state.livePrice ?: detail.price
        val change = state.liveChange ?: detail.changeAmount
        val changePercent = state.liveChangePct ?: detail.changePercent
        binding.tvPrice.text = String.format(Locale.US, "%.2f", price)
        val isPositive = change >= 0
        val priceColor = if (isPositive) R.color.color_positive else R.color.color_negative
        binding.tvPrice.setTextColor(ContextCompat.getColor(requireContext(), priceColor))

        val prefix = if (isPositive) "+" else ""
        binding.tvChangeAmount.text = String.format(Locale.US, "%s%.2f", prefix, change)
        binding.tvChangePercent.text = String.format(Locale.US, "%s%.2f%%", prefix, changePercent)
        binding.tvChangeAmount.setTextColor(ContextCompat.getColor(requireContext(), priceColor))
        binding.tvChangePercent.setTextColor(ContextCompat.getColor(requireContext(), priceColor))

        binding.tvVolCurrent.text = String.format(Locale.US, "%,d", state.liveVolume ?: detail.volume)
    }

    private fun bindCandles(candles: List<CandleEntry>) {
        val chart = candleChart ?: return
        val volChart = volumeChart ?: return

        if (candles.isEmpty()) {
            val symbolLabel = if (currentSymbol.isNotEmpty()) currentSymbol else "this stock"
            chart.setNoDataText("No historical price data available for $symbolLabel on PSX feed")
            chart.data = null
            chart.invalidate()
            volChart.setNoDataText("")
            volChart.data = null
            volChart.invalidate()
            return
        }

        val positiveColor = ContextCompat.getColor(requireContext(), R.color.color_positive)
        val negativeColor = ContextCompat.getColor(requireContext(), R.color.color_negative)

        // Candlestick entries
        val candleEntries = candles.mapIndexed { index, candle ->
            com.github.mikephil.charting.data.CandleEntry(
                index.toFloat(),
                candle.high,
                candle.low,
                candle.open,
                candle.close
            )
        }

        val candleDataSet = CandleDataSet(candleEntries, "OHLC").apply {
            setDrawValues(false)
            shadowColorSameAsCandle = true
            increasingColor = positiveColor
            increasingPaintStyle = Paint.Style.FILL
            decreasingColor = negativeColor
            decreasingPaintStyle = Paint.Style.FILL
            neutralColor = Color.GRAY
            shadowWidth = 1.0f
        }

        chart.data = CandleData(candleDataSet)
        val visibleRange = if (candleEntries.size > 25) 25f else candleEntries.size.toFloat().coerceAtLeast(5f)
        chart.setVisibleXRangeMaximum(visibleRange)
        chart.moveViewToX(candleEntries.size.toFloat())
        chart.invalidate()

        // Volume bar chart
        val barEntries = candles.mapIndexed { index, candle ->
            BarEntry(index.toFloat(), candle.volume.toFloat())
        }

        val barColors = candles.map { candle ->
            if (candle.close >= candle.open) positiveColor else negativeColor
        }

        val barDataSet = BarDataSet(barEntries, "Volume").apply {
            setDrawValues(false)
            colors = barColors
        }

        volChart.data = BarData(barDataSet).apply {
            barWidth = 0.8f
        }
        volChart.setVisibleXRangeMaximum(visibleRange)
        volChart.moveViewToX(barEntries.size.toFloat())
        volChart.invalidate()
    }

    private fun updateTimeframeTabs(selected: String) {
        val tabs = listOf(
            binding.tab1d to "1D",
            binding.tab1w to "1W",
            binding.tab1m to "1M",
            binding.tab1y to "1Y"
        )

        tabs.forEach { (tab, tf) ->
            val isActive = selected == tf
            tab.setBackgroundResource(if (isActive) R.drawable.bg_timeframe_active else 0)
            tab.setTextColor(
                ContextCompat.getColor(
                    requireContext(),
                    if (isActive) R.color.color_text_primary else R.color.color_text_secondary
                )
            )
        }
    }

    private fun updateSectionTabs(selected: String) {
        val sections = listOf(
            Triple(binding.tvTabQuotes, binding.indicatorQuotes, "Quotes"),
            Triple(binding.tvTabAnalysis, binding.indicatorAnalysis, "Analysis"),
            Triple(binding.tvTabNews, binding.indicatorNews, "News"),
            Triple(binding.tvTabProfile, binding.indicatorProfile, "Profile")
        )

        sections.forEach { (textView, indicator, name) ->
            val isActive = selected == name
            textView.setTextColor(
                ContextCompat.getColor(
                    requireContext(),
                    if (isActive) R.color.color_text_primary else R.color.color_text_secondary
                )
            )
            if (isActive) {
                textView.setTypeface(null, android.graphics.Typeface.BOLD)
            } else {
                textView.setTypeface(null, android.graphics.Typeface.NORMAL)
            }
            indicator.setBackgroundColor(
                ContextCompat.getColor(
                    requireContext(),
                    if (isActive) R.color.color_basarat_green else R.color.transparent
                )
            )
        }

        // Update sub pills based on section
        updateSubPillsVisibility(selected)
    }

    private fun updateSubPillsVisibility(section: String) {
        when (section) {
            "Quotes" -> {
                binding.pillByPrice.text = "By Price"
                binding.pillTrades.text = "Trades"
                binding.pillDetailedQuote.text = "Detailed Quote"
                binding.pillLiquidity.text = "Liquidity"
                binding.scrollSubPills.visibility = View.VISIBLE
            }
            "News" -> {
                binding.pillByPrice.text = "Latest"
                binding.pillTrades.text = "Sentiment"
                binding.pillDetailedQuote.text = "Events"
                binding.pillLiquidity.visibility = View.GONE
                binding.scrollSubPills.visibility = View.VISIBLE
            }
            "Profile" -> {
                binding.pillByPrice.text = "Overview"
                binding.pillTrades.text = "Financials"
                binding.pillDetailedQuote.text = "Board"
                binding.pillLiquidity.visibility = View.GONE
                binding.scrollSubPills.visibility = View.VISIBLE
            }
        }
    }

    private fun updateSubPills(selected: String) {
        val pills = listOf(
            binding.pillByPrice,
            binding.pillTrades,
            binding.pillDetailedQuote,
            binding.pillLiquidity
        )

        pills.forEach { pill ->
            if (pill.visibility != View.VISIBLE) return@forEach
            val isActive = pill.text.toString().equals(selected, ignoreCase = true)
            pill.setBackgroundResource(
                if (isActive) R.drawable.bg_chip_filter_selected else R.drawable.bg_chip_filter_unselected
            )
            pill.setTextColor(
                ContextCompat.getColor(
                    requireContext(),
                    if (isActive) R.color.color_positive else R.color.color_text_secondary
                )
            )
        }
    }

    // ───────────────────────────────
    //  BOTTOM TAB CONTENT
    // ───────────────────────────────

    private fun bindTabContent(state: StockDetailUiState.Success) {
        binding.containerTabContent.removeAllViews()

        when (state.selectedSection) {
            "Quotes" -> bindQuotesContent(state)
            "News" -> bindNewsContent(state)
            "Profile" -> bindProfileContent(state)
        }
    }

    private fun bindQuotesContent(state: StockDetailUiState.Success) {
        when (state.selectedSubPill) {
            "By Price" -> bindByPriceContent(state.detail)
            "Trades" -> bindTradesContent(state.trades)
            "Detailed Quote" -> bindDetailedQuoteContent(state.detail)
            "Liquidity" -> bindLiquidityContent(state.detail)
        }
    }

    private fun bindByPriceContent(detail: StockDetail) {
        val content = layoutInflater.inflate(R.layout.content_by_price, binding.containerTabContent, false)
        val rows = listOf(
            Pair("Open", String.format(Locale.US, "%.2f", detail.open)),
            Pair("High", String.format(Locale.US, "%.2f", detail.high)),
            Pair("Low", String.format(Locale.US, "%.2f", detail.low)),
            Pair("Close", String.format(Locale.US, "%.2f", detail.close)),
            Pair("Prev Close", String.format(Locale.US, "%.2f", detail.price - detail.changeAmount)),
            Pair("52W High", String.format(Locale.US, "%.2f", detail.high52Week)),
            Pair("52W Low", String.format(Locale.US, "%.2f", detail.low52Week))
        )
        val container = content.findViewById<android.widget.LinearLayout>(R.id.container_stats)
        rows.forEach { (label, value) ->
            addStatRow(container, label, value)
        }
        binding.containerTabContent.addView(content)
    }

    private fun bindTradesContent(trades: List<StockTrade>) {
        val rv = RecyclerView(requireContext()).apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = tradeAdapter
            isNestedScrollingEnabled = false
        }
        tradeAdapter.submitList(trades)
        binding.containerTabContent.addView(rv)
    }

    private fun bindDetailedQuoteContent(detail: StockDetail) {
        val content = layoutInflater.inflate(R.layout.content_by_price, binding.containerTabContent, false)
        val rows = listOf(
            Pair("Market Cap", detail.marketCap),
            Pair("P/E Ratio", String.format(Locale.US, "%.2f", detail.pe)),
            Pair("EPS", String.format(Locale.US, "%.2f", detail.eps)),
            Pair("Volume", String.format(Locale.US, "%,d", detail.volume)),
            Pair("Avg Volume", String.format(Locale.US, "%,d", detail.avgVolume)),
            Pair("Sector", detail.sector),
            Pair("Shariah", if (detail.isShariah) "Compliant ✓" else "Non-Compliant")
        )
        val container = content.findViewById<android.widget.LinearLayout>(R.id.container_stats)
        rows.forEach { (label, value) ->
            addStatRow(container, label, value)
        }
        binding.containerTabContent.addView(content)
    }

    private fun bindLiquidityContent(detail: StockDetail) {
        val content = layoutInflater.inflate(R.layout.content_by_price, binding.containerTabContent, false)
        val rows = listOf(
            Pair("Day Volume", String.format(Locale.US, "%,d", detail.volume)),
            Pair("Avg Volume (20d)", String.format(Locale.US, "%,d", detail.avgVolume)),
            Pair("Turnover", String.format(Locale.US, "PKR %.1fM", detail.price * detail.volume / 1_000_000)),
            Pair("Bid-Ask Spread", "0.15 (0.25%)"),
            Pair("Free Float", "42.5%"),
            Pair("Depth Score", "7.2 / 10")
        )
        val container = content.findViewById<android.widget.LinearLayout>(R.id.container_stats)
        rows.forEach { (label, value) ->
            addStatRow(container, label, value)
        }
        binding.containerTabContent.addView(content)
    }

    private fun bindNewsContent(state: StockDetailUiState.Success) {
        val sym = state.detail.symbol
        val rv = RecyclerView(requireContext()).apply {
            layoutManager = LinearLayoutManager(requireContext())
            isNestedScrollingEnabled = false
        }
        val stockNewsAdapter = NewsArticleAdapter { article ->
            val bundle = Bundle().apply { putString("articleId", article.id) }
            findNavController().navigate(R.id.action_stockDetail_to_articleDetail, bundle)
        }
        rv.adapter = stockNewsAdapter
        binding.containerTabContent.addView(rv)

        viewLifecycleOwner.lifecycleScope.launch {
            // Tab taps rebind this section, so reuse the list already fetched for this symbol
            // instead of re-requesting it each time the user returns to the News tab.
            val cached = stockNewsBySymbol[sym]
            val result = if (cached != null) {
                Result.success(cached)
            } else {
                NewsRepositoryImpl().getStockNews(symbol = sym, limit = 10)
                    .map { page -> page.articles.also { stockNewsBySymbol[sym] = it } }
            }
            result.fold(
                onSuccess = { articles ->
                    if (articles.isNotEmpty()) {
                        stockNewsAdapter.submitList(articles)
                    } else {
                        val emptyTv = TextView(requireContext()).apply {
                            text = "No recent news articles found for $sym"
                            setTextAppearance(requireContext(), R.style.TextAppearance_Basarat_Body_Small)
                            setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
                            setPadding(16, 32, 16, 32)
                        }
                        binding.containerTabContent.removeAllViews()
                        binding.containerTabContent.addView(emptyTv)
                    }
                },
                onFailure = {
                    val errorTv = TextView(requireContext()).apply {
                        text = "Unable to load news for $sym"
                        setTextAppearance(requireContext(), R.style.TextAppearance_Basarat_Body_Small)
                        setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
                        setPadding(16, 32, 16, 32)
                    }
                    binding.containerTabContent.removeAllViews()
                    binding.containerTabContent.addView(errorTv)
                }
            )
        }
    }

    private fun bindProfileContent(state: StockDetailUiState.Success) {
        val detail = state.detail
        val content = layoutInflater.inflate(R.layout.content_by_price, binding.containerTabContent, false)
        val container = content.findViewById<android.widget.LinearLayout>(R.id.container_stats)
        val rows = listOf(
            Pair("Company", detail.companyName),
            Pair("Symbol", detail.symbol),
            Pair("Code", detail.code),
            Pair("Sector", detail.sector),
            Pair("Market", "PSX"),
            Pair("Shariah Status", if (detail.isShariah) "KMI-30 Compliant ✓" else "Non-Compliant"),
            Pair("Dividend", if (detail.hasDividend) "Yes" else "No")
        )
        rows.forEach { (label, value) ->
            addStatRow(container, label, value)
        }
        binding.containerTabContent.addView(content)
    }

    private fun addStatRow(container: android.widget.LinearLayout, label: String, value: String) {
        val row = android.widget.LinearLayout(requireContext()).apply {
            orientation = android.widget.LinearLayout.HORIZONTAL
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            setPadding(0, 20, 0, 20)
        }

        val labelTv = TextView(requireContext()).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            text = label
            setTextAppearance(requireContext(), R.style.TextAppearance_Basarat_Body_Small)
            setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
        }

        val valueTv = TextView(requireContext()).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT,
                android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
            )
            text = value
            setTextAppearance(requireContext(), R.style.TextAppearance_Basarat_Number_Body_Small_Strong)
        }

        if (label.contains("Shariah", ignoreCase = true)) {
            valueTv.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_shariah_teal))
            row.isClickable = true
            val outVal = android.util.TypedValue()
            requireContext().theme.resolveAttribute(android.R.attr.selectableItemBackground, outVal, true)
            row.setBackgroundResource(outVal.resourceId)
            row.setOnClickListener {
                val sheet = com.fyp.basarattradeinvest.feature.shariah.details.StockShariahDetailsBottomSheet.newInstance(currentSymbol)
                sheet.show(childFragmentManager, "StockShariahDetailsBottomSheet")
            }
        }

        row.addView(labelTv)
        row.addView(valueTv)
        container.addView(row)

        // Divider
        val divider = View(requireContext()).apply {
            layoutParams = android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, 1
            )
            setBackgroundColor(ContextCompat.getColor(context, R.color.color_divider))
        }
        container.addView(divider)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        lastRenderedSuccess = null
        candleChart = null
        volumeChart = null
        _binding = null
    }
}
