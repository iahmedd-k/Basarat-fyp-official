package com.fyp.basarattradeinvest.feature.recommendation.detail

import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
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
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentStockRecommendationDetailBinding
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationComponent
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationDetail
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationSignal
import com.fyp.basarattradeinvest.domain.model.recommendations.TargetStop
import kotlinx.coroutines.launch
import java.util.Locale
import kotlin.math.roundToInt

class StockRecommendationDetailFragment : Fragment() {

    private var _binding: FragmentStockRecommendationDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: StockRecommendationDetailViewModel by activityViewModels()
    private var symbol: String = "OGDC"
    private var boundDetail: RecommendationDetail? = null
    private val expandedComponents = mutableSetOf<String>()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentStockRecommendationDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        symbol = arguments?.getString("symbol") ?: "OGDC"
        expandedComponents.clear()
        boundDetail = null

        setupListeners()
        observeUiState()

        viewModel.ensureLoaded(symbol)
    }

    private fun setupListeners() {
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.btnViewStock.setOnClickListener {
            val bundle = Bundle().apply { putString("symbol", symbol) }
            findNavController().navigate(R.id.stockDetailFragment, bundle)
        }

        binding.btnRetry.setOnClickListener {
            viewModel.retry()
        }

        binding.rowRiskProfile.setOnClickListener {
            findNavController().navigate(R.id.riskProfileFragment)
        }
        binding.btnChangeProfile.setOnClickListener {
            findNavController().navigate(R.id.riskProfileFragment)
        }
        binding.rowSignalWeights.setOnClickListener {
            findNavController().navigate(R.id.recommendationSettingsFragment)
        }
        binding.btnEditWeights.setOnClickListener {
            findNavController().navigate(R.id.recommendationSettingsFragment)
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    renderUiState(state)
                }
            }
        }
    }

    private fun renderUiState(state: StockRecommendationDetailUiState) {
        binding.layoutRecommendationSkeleton.visibility = View.GONE
        binding.layoutError.visibility = View.GONE
        binding.scrollContent.visibility = View.GONE

        when (state) {
            is StockRecommendationDetailUiState.Loading -> {
                binding.layoutRecommendationSkeleton.visibility = View.VISIBLE
            }
            is StockRecommendationDetailUiState.Success -> {
                binding.scrollContent.visibility = View.VISIBLE
                bindData(state.detail, state.targetStop)
            }
            is StockRecommendationDetailUiState.Error -> {
                binding.layoutError.visibility = View.VISIBLE
                binding.tvErrorMessage.text = state.message
            }
        }
    }

    private fun bindData(detail: RecommendationDetail, targetStop: TargetStop?) {
        val context = requireContext()

        binding.tvTitleSymbol.text = "${detail.symbol} Recommendation"
        binding.tvSymbol.text = detail.symbol
        val stockContext = listOfNotNull(detail.name?.takeIf { it != detail.symbol }, detail.sector)
            .joinToString(" · ")
        binding.tvStockContext.apply {
            text = stockContext
            visibility = if (stockContext.isNotBlank()) View.VISIBLE else View.GONE
        }
        binding.tvSignalBadge.text = detail.signal.label

        when (detail.signal) {
            RecommendationSignal.BUY -> {
                binding.tvSignalBadge.setBackgroundResource(R.drawable.bg_badge_positive)
                binding.tvSignalBadge.setTextColor(ContextCompat.getColor(context, R.color.color_positive))
            }
            RecommendationSignal.SELL -> {
                binding.tvSignalBadge.setBackgroundResource(R.drawable.bg_badge_negative)
                binding.tvSignalBadge.setTextColor(ContextCompat.getColor(context, R.color.color_negative))
            }
            RecommendationSignal.HOLD -> {
                binding.tvSignalBadge.setBackgroundResource(R.drawable.bg_badge_neutral)
                binding.tvSignalBadge.setTextColor(ContextCompat.getColor(context, R.color.color_neutral))
            }
        }

        val sign = if (detail.compositeScore >= 0) "+" else ""
        binding.tvCompositeScore.text = String.format(Locale.US, "Score: %s%.2f", sign, detail.compositeScore)
        binding.tvConfidenceLabel.text = String.format(Locale.US, "Signal confidence: %d%%", (detail.confidence * 100).toInt())

        if (detail.currentPrice != null) {
            binding.tvCurrentPrice.text = String.format(Locale.US, "Current Market Price: PKR %.2f", detail.currentPrice)
        } else if (targetStop?.currentPrice != null) {
            binding.tvCurrentPrice.text = String.format(Locale.US, "Current Market Price: PKR %.2f", targetStop.currentPrice)
        } else {
            binding.tvCurrentPrice.text = "Current Market Price: N/A"
        }

        val horizon = detail.horizon?.takeIf { it.isNotBlank() }?.let { "Outlook: $it" }
        val reason = (detail.suppressionReason ?: detail.decisionReason)
            ?.takeIf { it.isNotBlank() && !containsInternalModelName(it) }
        binding.tvDecisionReason.text = listOfNotNull(horizon, reason).joinToString("\n")
        binding.cardDecisionReason.visibility =
            if (binding.tvDecisionReason.text.isNotBlank()) View.VISIBLE else View.GONE
        renderComponents(detail)

        // Target / Stop Section
        val target = targetStop?.targetPrice ?: detail.targetPrice
        val stop = targetStop?.stopLoss ?: detail.stopLoss

        if (target != null) {
            binding.tvDetailTargetPrice.text = String.format(Locale.US, "PKR %.2f", target)
        } else {
            binding.tvDetailTargetPrice.text = "N/A"
        }

        if (stop != null) {
            binding.tvDetailStopLoss.text = String.format(Locale.US, "PKR %.2f", stop)
        } else {
            binding.tvDetailStopLoss.text = "N/A"
        }

        if (targetStop?.upsidePct != null) {
            val upsideSign = if (targetStop.upsidePct >= 0) "+" else ""
            binding.tvUpsidePct.text = String.format(Locale.US, "%s%.2f%% upside", upsideSign, targetStop.upsidePct)
            binding.tvUpsidePct.visibility = View.VISIBLE
        } else {
            binding.tvUpsidePct.visibility = View.GONE
        }

        if (targetStop?.downsidePct != null) {
            binding.tvDownsidePct.text = String.format(Locale.US, "%.2f%% downside", targetStop.downsidePct)
            binding.tvDownsidePct.visibility = View.VISIBLE
        } else {
            binding.tvDownsidePct.visibility = View.GONE
        }

        val expectedRange = targetStop?.expectedRange ?: detail.expectedRange
        val atr = targetStop?.atr14 ?: detail.atr14
        val price = detail.currentPrice ?: targetStop?.currentPrice
        if (expectedRange != null && expectedRange.high > expectedRange.low) {
            binding.tvExpectedRange.text = String.format(
                Locale.US,
                "Expected Range: PKR %.2f — PKR %.2f",
                expectedRange.low,
                expectedRange.high
            )
            binding.tvExpectedRange.visibility = View.VISIBLE
        } else {
            binding.tvExpectedRange.visibility = View.GONE
        }

        // ATR-14 against the last price is the typical one-session move; it is a volatility
        // reading, so it gets its own card instead of crowding the target/stop block.
        val dailyRangeVisible = atr != null && price != null && price > 0.0
        if (dailyRangeVisible) {
            binding.tvDailyRange.text = String.format(
                Locale.US,
                "PKR %.2f (%.1f%%)",
                atr,
                atr / price * 100.0
            )
        }
        binding.cardDailyRange.visibility = if (dailyRangeVisible) View.VISIBLE else View.GONE

        // When the live recompute withheld its verdict, the repository falls back to the
        // engine's published batch, so the levels here are the batch's, not a fresh reading.
        val levelsFromBatch = detail.isSuppressed && targetStop == null

        val riskNote = when {
            levelsFromBatch && target != null && stop != null -> "The latest published recommendation is shown; a refreshed signal is not available."
            target != null && stop != null -> "Risk estimates are for decision support and are not guaranteed outcomes."
            detail.suppressionReason?.isNotBlank() == true && !containsInternalModelName(detail.suppressionReason) -> "Target and stop levels were not provided: ${detail.suppressionReason}"
            targetStop?.method == "default" || expectedRange?.method == "default" -> "The backend returned a flat default range; no target or stop level is available."
            atr != null && !dailyRangeVisible -> "ATR-14: PKR ${String.format(Locale.US, "%.2f", atr)}. Volatility guide, not a target or stop-loss."
            else -> "Target and stop levels were not provided by the backend."
        }
        binding.tvRiskNote.apply {
            text = riskNote
            visibility = if (levelsFromBatch || target == null || stop == null || (atr != null && !dailyRangeVisible)) View.VISIBLE else View.GONE
        }

        bindEngineSettings(detail)
    }

    private fun bindEngineSettings(detail: RecommendationDetail) {
        val riskProfile = detail.riskProfile?.takeIf { it.isNotBlank() }?.let(::humanise)
        val weights = detail.weights
            .filterKeys { it.lowercase(Locale.ROOT) in WEIGHTED_COMPONENTS }
            .toList()
            .sortedBy { WEIGHT_ORDER.getValue(it.first.lowercase(Locale.ROOT)) }
            .map { (it.second * 100).roundToInt().toString() }
            .takeIf { it.isNotEmpty() }
            ?.joinToString(" / ")

        binding.tvRiskProfile.text = riskProfile.orEmpty()
        binding.rowRiskProfile.visibility = if (riskProfile != null) View.VISIBLE else View.GONE
        binding.tvSignalWeights.text = weights.orEmpty()
        binding.rowSignalWeights.visibility = if (weights != null) View.VISIBLE else View.GONE

        val hasRiskProfile = riskProfile != null
        val hasWeights = weights != null
        binding.dividerProfileWeights.visibility =
            if (hasRiskProfile && hasWeights) View.VISIBLE else View.GONE
        binding.cardProfileWeights.visibility =
            if (hasRiskProfile || hasWeights) View.VISIBLE else View.GONE
    }

    private fun renderComponents(detail: RecommendationDetail) {
        boundDetail = detail
        val rows = binding.layoutComponentRows
        rows.removeAllViews()

        val maxWeight = detail.components
            .mapNotNull { it.effectiveWeight ?: it.configuredWeight }
            .maxOrNull()
            ?.takeIf { it > 0 }

        detail.components.forEachIndexed { index, component ->
            if (index > 0) rows.addView(divider())
            rows.addView(componentRow(component, maxWeight))
        }

        binding.layoutSignalDrivers.visibility = if (detail.components.isNotEmpty()) View.VISIBLE else View.GONE
    }

    private fun componentRow(component: RecommendationComponent, maxWeight: Double?): View {
        val weight = component.effectiveWeight ?: component.configuredWeight

        val titleLine = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        titleLine.addView(text(componentLabel(component.key), 14f, R.color.color_text_primary, bold = true))
        titleLine.addView(
            text(
                weight?.let { String.format(Locale.US, "  ·  %.0f%% weight", it * 100) }.orEmpty(),
                12f,
                R.color.color_text_secondary
            )
        )
        titleLine.addView(View(requireContext()).apply {
            layoutParams = LinearLayout.LayoutParams(0, 1, 1f)
        })
        val score = component.score
        titleLine.addView(
            text(
                score?.let { String.format(Locale.US, "%+.2f", it) }
                    ?: component.status?.takeUnless(::containsInternalModelName)?.uppercase(Locale.ROOT) ?: "N/A",
                14f,
                when {
                    score == null -> R.color.color_text_tertiary
                    score > 0 -> R.color.color_positive
                    score < 0 -> R.color.color_negative
                    else -> R.color.color_text_secondary
                },
                bold = true
            )
        )

        val row = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(14), 0, dp(14))
            addView(titleLine)
        }

        // The bar only restates the weight label, scaled against the heaviest component so the
        // rows compare at a glance.
        if (weight != null && maxWeight != null) {
            val filled = (weight / maxWeight).toFloat().coerceIn(0.05f, 1f)
            row.addView(LinearLayout(requireContext()).apply {
                orientation = LinearLayout.HORIZONTAL
                setPadding(0, dp(9), 0, 0)
                addView(View(requireContext()).apply {
                    layoutParams = LinearLayout.LayoutParams(0, dp(3), filled)
                    setBackgroundColor(color(R.color.color_button_primary_bg))
                })
                addView(View(requireContext()).apply {
                    layoutParams = LinearLayout.LayoutParams(0, dp(3), 1f - filled)
                    setBackgroundColor(color(R.color.color_divider))
                })
            })
        }

        val evidence = component.details
            .filterNot { (key, value) -> containsInternalModelName(key) || containsInternalModelName(value) }
            .map { (key, value) ->
                val rendered = compactNumber(value)
                // The backend already names the field inside its own values (`rsi` -> "RSI=34.8"),
                // so prefixing it again reads as noise.
                if (rendered.startsWith(key, ignoreCase = true)) rendered else "${humanise(key)}: $rendered"
            }
            .ifEmpty { listOfNotNull(component.availabilityReason?.takeIf { it.isNotBlank() && !containsInternalModelName(it) }) }
        if (evidence.isNotEmpty()) {
            // The engine returns up to ten raw fields per component, which buries the signal.
            // Show the first few and let the rest expand in place — nothing is dropped.
            val expanded = component.key in expandedComponents
            val shown = if (expanded || evidence.size <= EVIDENCE_PREVIEW) {
                evidence
            } else {
                evidence.take(EVIDENCE_PREVIEW)
            }
            row.addView(text(shown.joinToString("\n"), 12f, R.color.color_text_secondary).apply {
                setPadding(0, dp(9), 0, 0)
                setLineSpacing(dp(3).toFloat(), 1f)
            })
            if (evidence.size > EVIDENCE_PREVIEW) {
                row.addView(
                    text(
                        if (expanded) "Show less" else "Show ${evidence.size - EVIDENCE_PREVIEW} more",
                        12f,
                        R.color.color_basarat_green,
                        bold = true
                    ).apply {
                        setPadding(0, dp(6), 0, 0)
                        setOnClickListener {
                            if (expanded) expandedComponents.remove(component.key) else expandedComponents.add(component.key)
                            boundDetail?.let { renderComponents(it) }
                        }
                    }
                )
            }
        }
        return row
    }

    private fun componentLabel(key: String): String = when {
        containsInternalModelName(key) -> "Price outlook"
        key.lowercase(Locale.ROOT) in setOf("ml", "gru") -> "Price outlook"
        key.equals("technical", ignoreCase = true) -> "Technical"
        key.equals("fundamental", ignoreCase = true) -> "Fundamentals"
        key.equals("sentiment", ignoreCase = true) -> "News sentiment"
        else -> humanise(key)
    }

    private fun humanise(key: String): String =
        key.replace('_', ' ').trim().replaceFirstChar { it.titlecase(Locale.ROOT) }

    private fun containsInternalModelName(value: String): Boolean =
        INTERNAL_MODEL_NAMES.any { modelName -> Regex("\\b${Regex.escape(modelName)}\\b", RegexOption.IGNORE_CASE).containsMatchIn(value) }

    /** Gson renders every JSON number as a Double, so `38.0` and `0.56` need tidying before display. */
    private fun compactNumber(value: String): String {
        val number = value.toDoubleOrNull() ?: return value
        return if (number % 1.0 == 0.0) {
            String.format(Locale.US, "%.0f", number)
        } else {
            String.format(Locale.US, "%.2f", number)
        }
    }

    private fun divider(): View = View(requireContext()).apply {
        setBackgroundColor(color(R.color.color_divider))
        layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(1))
    }

    private fun text(value: String, sizeSp: Float, colorRes: Int, bold: Boolean = false): TextView =
        TextView(requireContext()).apply {
            text = value
            textSize = sizeSp
            setTextColor(color(colorRes))
            if (bold) setTypeface(typeface, Typeface.BOLD)
        }

    private fun color(colorRes: Int): Int = ContextCompat.getColor(requireContext(), colorRes)

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private companion object {
        // `ml` and `gru` are two names the backend uses for the same forecast component.
        val WEIGHT_ORDER = mapOf(
            "ml" to 0,
            "gru" to 0,
            "technical" to 1,
            "fundamental" to 2,
            "sentiment" to 3
        )
        val WEIGHTED_COMPONENTS = WEIGHT_ORDER.keys

        const val EVIDENCE_PREVIEW = 3
        val INTERNAL_MODEL_NAMES = listOf("gru", "xgboost", "lstm", "random forest")
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
