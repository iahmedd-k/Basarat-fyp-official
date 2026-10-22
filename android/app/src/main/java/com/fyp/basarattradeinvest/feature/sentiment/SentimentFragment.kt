package com.fyp.basarattradeinvest.feature.sentiment

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentSentimentBinding
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentimentOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentHistory
import com.fyp.basarattradeinvest.domain.model.sentiment.StockSentiment
import com.fyp.basarattradeinvest.feature.sentiment.adapter.SentimentNewsAdapter
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter
import kotlinx.coroutines.launch
import java.util.Locale

/**
 * SentimentFragment
 *
 * Displays all four sentiment sections:
 *   1. Market Sentiment (GET /api/v1/sentiment/market-overview)
 *   2. Stock Sentiment  (GET /api/v1/sentiment/{symbol})
 *   3. Sentiment History Chart (GET /api/v1/sentiment/{symbol}/history)
 *   4. Sentiment News   (GET /api/v1/sentiment/{symbol}/news) with pagination
 *
 * Each section loads and fails independently.
 * Receives `symbol` from navigation arguments.
 */
class SentimentFragment : Fragment() {

    private var _binding: FragmentSentimentBinding? = null
    private val binding get() = _binding!!

    private val viewModel: SentimentViewModel by viewModels()
    private val newsAdapter by lazy { SentimentNewsAdapter() }

    private var currentSymbol: String = ""

    private var lastRenderedMarketSentiment: MarketSentimentSectionState? = null
    private var lastRenderedStockSentiment: StockSentimentSectionState? = null
    private var lastRenderedHistory: SentimentHistorySectionState? = null
    private var lastRenderedNews: SentimentNewsSectionState? = null
    private var lastRenderedPeriod: String? = null

    // Available periods per OpenAPI spec pattern constraint
    private val periods = listOf("1D", "1W", "1M", "3M", "6M", "1Y")

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentSentimentBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        currentSymbol = arguments?.getString("symbol") ?: ""
        binding.tvSymbolSubtitle.text = currentSymbol

        setupNewsRecyclerView()
        setupClickListeners()
        observeState()

        viewModel.loadAll(currentSymbol)
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  SETUP
    // ─────────────────────────────────────────────────────────────────────────

    private fun setupNewsRecyclerView() {
        binding.rvSentimentNews.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = newsAdapter
            isNestedScrollingEnabled = false
        }
    }

    private fun setupClickListeners() {
        binding.ivBack.setOnClickListener { findNavController().navigateUp() }

        // Retry buttons — each section has its own
        binding.btnMarketRetry.setOnClickListener { viewModel.retryMarketSentiment() }
        binding.btnStockSentimentRetry.setOnClickListener { viewModel.retryStockSentiment() }
        binding.btnHistoryRetry.setOnClickListener { viewModel.retryHistory() }
        binding.btnNewsRetry.setOnClickListener { viewModel.retryNews() }

        // Load more news button
        binding.btnLoadMoreNews.setOnClickListener { viewModel.loadMoreNews() }

        // Period pills
        setupPeriodPills()
    }

    private fun setupPeriodPills() {
        val pillMap = mapOf(
            "1D" to binding.pillPeriod1d,
            "1W" to binding.pillPeriod1w,
            "1M" to binding.pillPeriod1m,
            "3M" to binding.pillPeriod3m,
            "6M" to binding.pillPeriod6m,
            "1Y" to binding.pillPeriod1y
        )
        pillMap.forEach { (period, pill) ->
            pill.setOnClickListener { viewModel.selectPeriod(period) }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  STATE OBSERVATION
    // ─────────────────────────────────────────────────────────────────────────

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    // Each section arrives as its own emission; rebinding all four every time
                    // rebuilt the history chart and restarted its entry animation.
                    if (state.marketSentiment != lastRenderedMarketSentiment) {
                        renderMarketSentiment(state.marketSentiment)
                        lastRenderedMarketSentiment = state.marketSentiment
                    }
                    if (state.stockSentiment != lastRenderedStockSentiment) {
                        renderStockSentiment(state.stockSentiment)
                        lastRenderedStockSentiment = state.stockSentiment
                    }
                    if (state.history != lastRenderedHistory) {
                        renderHistory(state.history)
                        lastRenderedHistory = state.history
                    }
                    if (state.news != lastRenderedNews) {
                        renderNews(state.news)
                        lastRenderedNews = state.news
                    }
                    if (state.selectedPeriod != lastRenderedPeriod) {
                        updatePeriodPills(state.selectedPeriod)
                        lastRenderedPeriod = state.selectedPeriod
                    }
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  MARKET SENTIMENT
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderMarketSentiment(state: MarketSentimentSectionState) {
        when (state) {
            is MarketSentimentSectionState.Loading -> {
                binding.progressMarket.visibility = View.VISIBLE
                binding.layoutMarketError.visibility = View.GONE
                binding.cardMarketSentiment.visibility = View.GONE
            }
            is MarketSentimentSectionState.Error -> {
                binding.progressMarket.visibility = View.GONE
                binding.layoutMarketError.visibility = View.VISIBLE
                binding.cardMarketSentiment.visibility = View.GONE
                binding.tvMarketErrorMsg.text = state.message
            }
            is MarketSentimentSectionState.Empty -> {
                binding.progressMarket.visibility = View.GONE
                binding.layoutMarketError.visibility = View.GONE
                binding.cardMarketSentiment.visibility = View.GONE
            }
            is MarketSentimentSectionState.Success -> {
                binding.progressMarket.visibility = View.GONE
                binding.layoutMarketError.visibility = View.GONE
                binding.cardMarketSentiment.visibility = View.VISIBLE
                bindMarketData(state.data)
            }
        }
    }

    private fun bindMarketData(data: MarketSentimentOverview) {
        val ctx = requireContext()
        val moodLabel = data.marketMood.uppercase(Locale.getDefault())

        binding.tvMarketMood.text = moodLabel

        // Mood badge — color per BASARAT semantic colors
        binding.tvMarketMoodBadge.text = moodLabel
        val (bgRes, colorRes) = when {
            data.marketMood.contains("bullish", ignoreCase = true) ->
                Pair(R.drawable.bg_badge_positive, R.color.color_positive)
            data.marketMood.contains("bearish", ignoreCase = true) ->
                Pair(R.drawable.bg_badge_negative, R.color.color_negative)
            else ->
                Pair(R.drawable.bg_badge_neutral, R.color.color_text_secondary)
        }
        binding.tvMarketMoodBadge.setBackgroundResource(bgRes)
        binding.tvMarketMoodBadge.setTextColor(ContextCompat.getColor(ctx, colorRes))

        // Overall score (-1.0 to +1.0)
        binding.tvMarketOverallScore.text = String.format(
            Locale.US, "Overall Score: %+.2f  (scale: −1.0 to +1.0)", data.overallScore
        )

        // Advance / Decline / Unchanged
        binding.tvMarketAdvancing.text = data.advancing.toString()
        binding.tvMarketDeclining.text = data.declining.toString()
        binding.tvMarketUnchanged.text = data.unchanged.toString()

        // A/D ratio
        binding.tvMarketAdRatio.text = String.format(Locale.US, "A/D Ratio: %.2f", data.advanceDeclineRatio)

        // Article count
        binding.tvMarketArticleCount.text = "Articles: ${data.articleCount}"

        // Averages
        binding.tvMarketNewsAvg.text = String.format(Locale.US, "News Avg: %+.2f", data.newsSentimentAvg)
        binding.tvMarketCommunityAvg.text = String.format(Locale.US, "Community Avg: %+.2f", data.communitySentimentAvg)
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  STOCK SENTIMENT
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
                bindStockSentimentData(state.data)
            }
        }
    }

    private fun bindStockSentimentData(data: StockSentiment) {
        val ctx = requireContext()
        val labelUpper = data.label.uppercase(Locale.getDefault())

        // Label
        binding.tvStockLabel.text = labelUpper

        // Score: -1.0 to +1.0, format as +0.35 / -0.12 etc.
        val scoreText = String.format(Locale.US, "%+.2f", data.score)
        binding.tvStockScoreValue.text = scoreText
        val scoreColor = when {
            data.score > 0f -> ContextCompat.getColor(ctx, R.color.color_positive)
            data.score < 0f -> ContextCompat.getColor(ctx, R.color.color_negative)
            else -> ContextCompat.getColor(ctx, R.color.color_text_secondary)
        }
        binding.tvStockScoreValue.setTextColor(scoreColor)

        // Score bar: map -1.0..+1.0 onto 0..100% of bar width
        // Neutral (0.0) = 50%, Bullish (+1.0) = 100%, Bearish (-1.0) = 0%
        val pct = ((data.score + 1f) / 2f).coerceIn(0f, 1f)
        binding.viewScoreFill.post {
            val totalWidth = binding.viewScoreFill.parent.let {
                (it as View).width
            }
            val fillWidth = (pct * totalWidth).toInt()
            val params = binding.viewScoreFill.layoutParams
            params.width = fillWidth
            binding.viewScoreFill.layoutParams = params

            val barColor = when {
                data.score > 0.1f -> ContextCompat.getColor(ctx, R.color.color_positive)
                data.score < -0.1f -> ContextCompat.getColor(ctx, R.color.color_negative)
                else -> ContextCompat.getColor(ctx, R.color.color_text_secondary)
            }
            binding.viewScoreFill.setBackgroundColor(barColor)
        }

        // Article count
        binding.tvStockArticleCount.text = "Articles Analyzed: ${data.articleCount}"

        // Trend
        val trendIcon = when (data.trend.lowercase(Locale.getDefault())) {
            "improving" -> "↑"
            "declining" -> "↓"
            else -> "→"
        }
        binding.tvStockTrend.text = "Trend: ${data.trend.replaceFirstChar { it.uppercase() }} $trendIcon"

        // Source breakdown (only if data is meaningful)
        if (data.newsSourceCount > 0 || data.communitySourceCount > 0) {
            binding.layoutSourceBreakdown.visibility = View.VISIBLE
            binding.tvNewsSourceCount.text = "News: ${data.newsSourceCount} articles"
            binding.tvCommunitySourceCount.text = "Community: ${data.communitySourceCount} posts"
        } else {
            binding.layoutSourceBreakdown.visibility = View.GONE
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  SENTIMENT HISTORY CHART
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderHistory(state: SentimentHistorySectionState) {
        when (state) {
            is SentimentHistorySectionState.Loading -> {
                binding.progressHistory.visibility = View.VISIBLE
                binding.layoutHistoryError.visibility = View.GONE
                binding.tvHistoryEmpty.visibility = View.GONE
                binding.chartSentimentHistory.visibility = View.GONE
            }
            is SentimentHistorySectionState.Error -> {
                binding.progressHistory.visibility = View.GONE
                binding.layoutHistoryError.visibility = View.VISIBLE
                binding.tvHistoryEmpty.visibility = View.GONE
                binding.chartSentimentHistory.visibility = View.GONE
                binding.tvHistoryErrorMsg.text = state.message
            }
            is SentimentHistorySectionState.Empty -> {
                binding.progressHistory.visibility = View.GONE
                binding.layoutHistoryError.visibility = View.GONE
                binding.tvHistoryEmpty.visibility = View.VISIBLE
                binding.chartSentimentHistory.visibility = View.GONE
            }
            is SentimentHistorySectionState.Success -> {
                binding.progressHistory.visibility = View.GONE
                binding.layoutHistoryError.visibility = View.GONE
                binding.tvHistoryEmpty.visibility = View.GONE
                binding.chartSentimentHistory.visibility = View.VISIBLE
                renderHistoryChart(state.data)
            }
        }
    }

    private fun renderHistoryChart(history: SentimentHistory) {
        val chart = binding.chartSentimentHistory
        val ctx = requireContext()

        val chartTextColor = ContextCompat.getColor(ctx, R.color.color_text_secondary)
        val chartGridColor = ContextCompat.getColor(ctx, R.color.color_divider)
        val greenColor = ContextCompat.getColor(ctx, R.color.color_basarat_green)

        // X-axis labels: use date strings from the data
        val dateLabels = history.data.map { it.date }

        // Y-axis entries: score values (-1.0 to +1.0)
        val entries = history.data.mapIndexed { index, point ->
            Entry(index.toFloat(), point.score)
        }

        if (entries.isEmpty()) {
            chart.visibility = View.GONE
            binding.tvHistoryEmpty.visibility = View.VISIBLE
            return
        }

        val dataSet = LineDataSet(entries, "Sentiment Score").apply {
            color = greenColor
            setCircleColor(greenColor)
            circleRadius = 2f
            setDrawCircleHole(false)
            setDrawValues(false)
            lineWidth = 2f
            mode = LineDataSet.Mode.CUBIC_BEZIER
            // Fill below line
            setDrawFilled(true)
            fillAlpha = 30
            fillColor = greenColor
        }

        chart.apply {
            data = LineData(dataSet)
            description.isEnabled = false
            legend.isEnabled = false
            setTouchEnabled(true)
            setScaleEnabled(true)
            setPinchZoom(true)
            setBackgroundColor(Color.TRANSPARENT)

            xAxis.apply {
                position = XAxis.XAxisPosition.BOTTOM
                textColor = chartTextColor
                gridColor = chartGridColor
                setLabelCount(5, true)
                granularity = 1f
                valueFormatter = IndexAxisValueFormatter(dateLabels)
                setAvoidFirstLastClipping(true)
                textSize = 9f
            }

            axisLeft.apply {
                textColor = chartTextColor
                gridColor = chartGridColor
                axisMinimum = -1f
                axisMaximum = 1f
                // Show 0 line clearly (neutral)
                setDrawZeroLine(true)
                zeroLineColor = ContextCompat.getColor(ctx, R.color.color_text_secondary)
                zeroLineWidth = 1f
                textSize = 9f
            }

            axisRight.isEnabled = false
            animateX(500)
            invalidate()
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  SENTIMENT NEWS
    // ─────────────────────────────────────────────────────────────────────────

    private fun renderNews(state: SentimentNewsSectionState) {
        when (state) {
            is SentimentNewsSectionState.Loading -> {
                binding.progressNews.visibility = View.VISIBLE
                binding.layoutNewsError.visibility = View.GONE
                binding.tvNewsEmpty.visibility = View.GONE
                binding.rvSentimentNews.visibility = View.GONE
                binding.btnLoadMoreNews.visibility = View.GONE
                binding.progressNewsMore.visibility = View.GONE
            }
            is SentimentNewsSectionState.Error -> {
                binding.progressNews.visibility = View.GONE
                binding.layoutNewsError.visibility = View.VISIBLE
                binding.tvNewsEmpty.visibility = View.GONE
                binding.rvSentimentNews.visibility = View.GONE
                binding.btnLoadMoreNews.visibility = View.GONE
                binding.progressNewsMore.visibility = View.GONE
                binding.tvNewsErrorMsg.text = state.message
            }
            is SentimentNewsSectionState.Empty -> {
                binding.progressNews.visibility = View.GONE
                binding.layoutNewsError.visibility = View.GONE
                binding.tvNewsEmpty.visibility = View.VISIBLE
                binding.rvSentimentNews.visibility = View.GONE
                binding.btnLoadMoreNews.visibility = View.GONE
                binding.progressNewsMore.visibility = View.GONE
            }
            is SentimentNewsSectionState.Success -> {
                binding.progressNews.visibility = View.GONE
                binding.layoutNewsError.visibility = View.GONE
                binding.tvNewsEmpty.visibility = View.GONE
                binding.rvSentimentNews.visibility = View.VISIBLE

                newsAdapter.submitList(state.items)

                // Load more / loading more indicator
                if (state.isLoadingMore) {
                    binding.btnLoadMoreNews.visibility = View.GONE
                    binding.progressNewsMore.visibility = View.VISIBLE
                } else {
                    binding.progressNewsMore.visibility = View.GONE
                    binding.btnLoadMoreNews.visibility = if (state.hasMore) View.VISIBLE else View.GONE
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────────
    //  PERIOD PILL STYLING
    // ─────────────────────────────────────────────────────────────────────────

    private fun updatePeriodPills(selectedPeriod: String) {
        val pillMap = mapOf(
            "1D" to binding.pillPeriod1d,
            "1W" to binding.pillPeriod1w,
            "1M" to binding.pillPeriod1m,
            "3M" to binding.pillPeriod3m,
            "6M" to binding.pillPeriod6m,
            "1Y" to binding.pillPeriod1y
        )
        val primaryColor = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val secondaryColor = ContextCompat.getColor(requireContext(), R.color.color_text_secondary)

        pillMap.forEach { (period, pill) ->
            val isActive = period == selectedPeriod
            pill.setBackgroundResource(
                if (isActive) R.drawable.bg_chip_filter_selected
                else R.drawable.bg_chip_filter_unselected
            )
            pill.setTextColor(if (isActive) primaryColor else secondaryColor)
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
