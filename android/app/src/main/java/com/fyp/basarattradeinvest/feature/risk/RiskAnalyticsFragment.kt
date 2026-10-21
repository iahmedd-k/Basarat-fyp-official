package com.fyp.basarattradeinvest.feature.risk

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
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
import com.fyp.basarattradeinvest.databinding.FragmentRiskAnalyticsBinding
import com.fyp.basarattradeinvest.domain.model.risk.MonteCarloResult
import com.fyp.basarattradeinvest.domain.model.risk.PortfolioVaR
import com.fyp.basarattradeinvest.domain.model.risk.StressTestResult
import com.fyp.basarattradeinvest.feature.risk.adapter.HoldingImpactAdapter
import com.fyp.basarattradeinvest.feature.risk.adapter.MonteCarloPercentilesAdapter
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

class RiskAnalyticsFragment : Fragment() {

    private var _binding: FragmentRiskAnalyticsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: RiskAnalyticsViewModel by activityViewModels()

    private lateinit var mcPercentilesAdapter: MonteCarloPercentilesAdapter
    private lateinit var holdingImpactAdapter: HoldingImpactAdapter

    private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentRiskAnalyticsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerViews()
        setupListeners()
        observeState()
    }

    private fun setupRecyclerViews() {
        mcPercentilesAdapter = MonteCarloPercentilesAdapter()
        binding.rvMcPercentiles.layoutManager = LinearLayoutManager(requireContext(), LinearLayoutManager.HORIZONTAL, false)
        binding.rvMcPercentiles.adapter = mcPercentilesAdapter

        holdingImpactAdapter = HoldingImpactAdapter()
        binding.rvHoldingImpacts.layoutManager = LinearLayoutManager(requireContext())
        binding.rvHoldingImpacts.adapter = holdingImpactAdapter
    }

    private fun setupListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        // Horizon filter chips
        binding.chipHoriz1d.setOnClickListener { selectHorizon("1D") }
        binding.chipHoriz1w.setOnClickListener { selectHorizon("1W") }
        binding.chipHoriz1m.setOnClickListener { selectHorizon("1M") }

        // Confidence filter chips
        binding.chipConf90.setOnClickListener { selectConfidence(90) }
        binding.chipConf95.setOnClickListener { selectConfidence(95) }
        binding.chipConf99.setOnClickListener { selectConfidence(99) }

        binding.btnRetryVar.setOnClickListener {
            viewModel.loadVaR()
        }

        // Monte Carlo Run Simulation
        binding.btnRunMonteCarlo.setOnClickListener {
            val simulations = binding.etNumSimulations.text?.toString()?.toIntOrNull() ?: 1000
            val horizon = binding.etHorizonDays.text?.toString()?.toIntOrNull() ?: 30
            viewModel.startMonteCarlo(numSimulations = simulations, horizonDays = horizon)
        }

        // Scenario chips
        binding.chipScenario2008.setOnClickListener { selectScenario("2008_crash") }
        binding.chipScenarioCovid.setOnClickListener { selectScenario("covid_crash") }
        binding.chipScenarioPkr.setOnClickListener { selectScenario("pkr_devaluation") }
        binding.chipScenarioRate.setOnClickListener { selectScenario("interest_rate_hike") }

        binding.btnRetryStress.setOnClickListener {
            viewModel.loadStressTest()
        }
    }

    private fun selectHorizon(horizon: String) {
        updateChipSelection(
            selectedView = when (horizon) {
                "1D" -> binding.chipHoriz1d
                "1W" -> binding.chipHoriz1w
                "1M" -> binding.chipHoriz1m
                else -> binding.chipHoriz1d
            },
            allViews = listOf(binding.chipHoriz1d, binding.chipHoriz1w, binding.chipHoriz1m)
        )
        viewModel.loadVaR(horizon = horizon)
    }

    private fun selectConfidence(conf: Int) {
        updateChipSelection(
            selectedView = when (conf) {
                90 -> binding.chipConf90
                95 -> binding.chipConf95
                99 -> binding.chipConf99
                else -> binding.chipConf95
            },
            allViews = listOf(binding.chipConf90, binding.chipConf95, binding.chipConf99)
        )
        viewModel.loadVaR(confidence = conf)
    }

    private fun selectScenario(scenario: String) {
        updateChipSelection(
            selectedView = when (scenario) {
                "2008_crash" -> binding.chipScenario2008
                "covid_crash" -> binding.chipScenarioCovid
                "pkr_devaluation" -> binding.chipScenarioPkr
                "interest_rate_hike" -> binding.chipScenarioRate
                else -> binding.chipScenario2008
            },
            allViews = listOf(binding.chipScenario2008, binding.chipScenarioCovid, binding.chipScenarioPkr, binding.chipScenarioRate)
        )
        viewModel.loadStressTest(scenario = scenario)
    }

    private fun updateChipSelection(selectedView: TextView, allViews: List<TextView>) {
        allViews.forEach { view ->
            if (view == selectedView) {
                view.setBackgroundResource(R.drawable.bg_tab_selected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_button_primary_text))
            } else {
                view.setBackgroundResource(R.drawable.bg_tab_unselected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
            }
        }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    renderVaRState(state.varState, state.selectedConfidence, state.selectedHorizon)
                    renderMonteCarloState(state.monteCarloState)
                    renderStressTestState(state.stressTestState)
                }
            }
        }
    }

    private fun renderVaRState(varState: VaRUiState, conf: Int, horizon: String) {
        when (varState) {
            is VaRUiState.Loading -> {
                binding.progressVar.visibility = View.VISIBLE
                binding.layoutVarError.visibility = View.GONE
                binding.layoutVarContent.visibility = View.GONE
            }
            is VaRUiState.Error -> {
                binding.progressVar.visibility = View.GONE
                binding.layoutVarError.visibility = View.VISIBLE
                binding.layoutVarContent.visibility = View.GONE
                binding.tvVarError.text = varState.message
            }
            is VaRUiState.Success -> {
                binding.progressVar.visibility = View.GONE
                binding.layoutVarError.visibility = View.GONE
                binding.layoutVarContent.visibility = View.VISIBLE
                displayVaRData(varState.data, conf, horizon)
            }
        }
    }

    private fun displayVaRData(data: PortfolioVaR, conf: Int, horizon: String) {
        val varPct = data.varValue * 100
        val cvarPct = data.cvarValue * 100

        binding.tvVarValue.text = String.format(Locale.US, "%.2f%%", varPct)
        binding.tvCvarValue.text = String.format(Locale.US, "%.2f%%", cvarPct)
        binding.tvVarDesc.text = "Max expected loss at $conf% conf ($horizon horizon)"

        val volPct = data.annualizedVolatility * 100
        binding.tvVolatilityValue.text = String.format(Locale.US, "%.2f%%", volPct)
        binding.tvObservationsValue.text = "${data.numObservations} trading days"
    }

    private fun renderMonteCarloState(mcState: MonteCarloUiState) {
        when (mcState) {
            is MonteCarloUiState.Idle -> {
                binding.layoutMcProgress.visibility = View.GONE
                binding.tvMcError.visibility = View.GONE
                binding.layoutMcResult.visibility = View.GONE
                binding.btnRunMonteCarlo.isEnabled = true
            }
            is MonteCarloUiState.Starting -> {
                binding.layoutMcProgress.visibility = View.VISIBLE
                binding.tvMcStatus.text = "Initiating Monte Carlo simulation..."
                binding.tvMcError.visibility = View.GONE
                binding.layoutMcResult.visibility = View.GONE
                binding.btnRunMonteCarlo.isEnabled = false
            }
            is MonteCarloUiState.Polling -> {
                binding.layoutMcProgress.visibility = View.VISIBLE
                binding.tvMcStatus.text = "Simulating trajectories (Job #${mcState.taskId}, attempt ${mcState.attempts})..."
                binding.tvMcError.visibility = View.GONE
                binding.btnRunMonteCarlo.isEnabled = false
            }
            is MonteCarloUiState.Error -> {
                binding.layoutMcProgress.visibility = View.GONE
                binding.tvMcError.visibility = View.VISIBLE
                binding.tvMcError.text = mcState.message
                binding.layoutMcResult.visibility = View.GONE
                binding.btnRunMonteCarlo.isEnabled = true
            }
            is MonteCarloUiState.Success -> {
                binding.layoutMcProgress.visibility = View.GONE
                binding.tvMcError.visibility = View.GONE
                binding.layoutMcResult.visibility = View.VISIBLE
                binding.btnRunMonteCarlo.isEnabled = true
                displayMonteCarloResult(mcState.result)
            }
        }
    }

    private fun displayMonteCarloResult(result: MonteCarloResult) {
        mcPercentilesAdapter.submitList(result.percentiles)

        val stats = result.stats
        stats.meanReturn?.let {
            val prefix = if (it > 0) "+" else ""
            binding.tvMcMeanReturn.text = String.format(Locale.US, "%s%.2f%%", prefix, it * 100)
            binding.tvMcMeanReturn.setTextColor(if (it >= 0) Color.parseColor("#18B981") else Color.parseColor("#EF4444"))
        } ?: run {
            binding.tvMcMeanReturn.text = "N/A"
        }

        stats.probLoss?.let {
            binding.tvMcProbLoss.text = String.format(Locale.US, "%.1f%%", it * 100)
        } ?: run {
            binding.tvMcProbLoss.text = "N/A"
        }

        stats.maxDrawdown?.let {
            binding.tvMcMaxDrawdown.text = String.format(Locale.US, "%.1f%%", it * 100)
        } ?: run {
            binding.tvMcMaxDrawdown.text = "N/A"
        }

        stats.bestCase?.let {
            val prefix = if (it > 0) "+" else ""
            binding.tvMcBestCase.text = String.format(Locale.US, "%s%.1f%%", prefix, it * 100)
        } ?: run {
            binding.tvMcBestCase.text = "N/A"
        }
    }

    private fun renderStressTestState(stressState: StressTestUiState) {
        when (stressState) {
            is StressTestUiState.Loading -> {
                binding.progressStressTest.visibility = View.VISIBLE
                binding.layoutStressError.visibility = View.GONE
                binding.layoutStressContent.visibility = View.GONE
            }
            is StressTestUiState.Error -> {
                binding.progressStressTest.visibility = View.GONE
                binding.layoutStressError.visibility = View.VISIBLE
                binding.layoutStressContent.visibility = View.GONE
                binding.tvStressError.text = stressState.message
            }
            is StressTestUiState.Success -> {
                binding.progressStressTest.visibility = View.GONE
                binding.layoutStressError.visibility = View.GONE
                binding.layoutStressContent.visibility = View.VISIBLE
                displayStressTestResult(stressState.result)
            }
        }
    }

    private fun displayStressTestResult(result: StressTestResult) {
        binding.tvStressName.text = result.name
        binding.tvStressDesc.text = result.description

        val impactPct = result.portfolioImpact * 100
        val prefix = if (impactPct > 0) "+" else ""
        binding.tvStressImpactPct.text = String.format(Locale.US, "%s%.1f%%", prefix, impactPct)

        val impactVal = result.portfolioImpactValue
        val valPrefix = if (impactVal > 0) "+PKR " else "-PKR "
        binding.tvStressImpactValue.text = String.format(Locale.US, "%s%s", valPrefix, currencyFormat.format(Math.abs(impactVal)))

        binding.tvStressStressedVal.text = "PKR ${currencyFormat.format(result.stressedValue)}"
        binding.tvStressCurrentVal.text = "Current: PKR ${currencyFormat.format(result.currentValue)}"

        binding.tvStressWorstLoss.text = String.format(Locale.US, "%.1f%%", result.worstCaseLoss * 100)
        binding.tvStressVolMult.text = String.format(Locale.US, "%.1fx", result.volatilityMultiplier)
        binding.tvStressRecoveryDays.text = "${result.recoveryDays} Days"

        holdingImpactAdapter.submitList(result.holdingImpacts)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
