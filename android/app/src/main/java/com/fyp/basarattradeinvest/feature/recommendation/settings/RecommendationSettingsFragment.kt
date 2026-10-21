package com.fyp.basarattradeinvest.feature.recommendation.settings

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.databinding.FragmentRecommendationSettingsBinding
import com.fyp.basarattradeinvest.domain.model.recommendations.EngineWeights
import kotlinx.coroutines.launch
import java.util.Locale

class RecommendationSettingsFragment : Fragment() {

    private var _binding: FragmentRecommendationSettingsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: RecommendationSettingsViewModel by activityViewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentRecommendationSettingsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupListeners()
        observeUiState()
    }

    private fun setupListeners() {
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.sliderGru.addOnChangeListener { _, value, _ ->
            binding.tvGruWeightVal.text = "${value.toInt()}%"
            updateTotalWeight()
        }

        binding.sliderTech.addOnChangeListener { _, value, _ ->
            binding.tvTechWeightVal.text = "${value.toInt()}%"
            updateTotalWeight()
        }

        binding.sliderFund.addOnChangeListener { _, value, _ ->
            binding.tvFundWeightVal.text = "${value.toInt()}%"
            updateTotalWeight()
        }

        binding.btnSaveWeights.setOnClickListener {
            val gruRaw = binding.sliderGru.value.toDouble()
            val techRaw = binding.sliderTech.value.toDouble()
            val fundRaw = binding.sliderFund.value.toDouble()
            val sum = gruRaw + techRaw + fundRaw

            val gruNorm = if (sum > 0) gruRaw / sum else 0.33
            val techNorm = if (sum > 0) techRaw / sum else 0.33
            val fundNorm = if (sum > 0) fundRaw / sum else 0.34

            viewModel.saveWeights(gruNorm, techNorm, fundNorm)
        }

        binding.btnResetDefaults.setOnClickListener {
            viewModel.resetToDefaults()
        }
    }

    private fun updateTotalWeight() {
        val gru = binding.sliderGru.value.toInt()
        val tech = binding.sliderTech.value.toInt()
        val fund = binding.sliderFund.value.toInt()
        val total = gru + tech + fund
        binding.tvTotalWeight.text = "Total: $total% (Normalized automatically on apply)"
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

    private fun renderUiState(state: RecommendationSettingsUiState) {
        when (state) {
            is RecommendationSettingsUiState.Loading -> {
                binding.pbLoading.visibility = View.VISIBLE
                binding.scrollContent.visibility = View.GONE
            }
            is RecommendationSettingsUiState.Loaded -> {
                binding.pbLoading.visibility = View.GONE
                binding.scrollContent.visibility = View.VISIBLE
                binding.btnSaveWeights.isEnabled = !state.isSaving

                setSliderValues(state.weights)

                state.saveMessage?.let {
                    Toast.makeText(requireContext(), it, Toast.LENGTH_SHORT).show()
                }
            }
            is RecommendationSettingsUiState.Error -> {
                binding.pbLoading.visibility = View.GONE
                // Sliders keep their XML defaults, so the toast has to say they are not the backend's values.
                binding.scrollContent.visibility = View.VISIBLE
                Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun setSliderValues(weights: EngineWeights) {
        val gruPct = (weights.gruWeight * 100).toInt().coerceIn(0, 100)
        val techPct = (weights.technicalWeight * 100).toInt().coerceIn(0, 100)
        val fundPct = (weights.fundamentalWeight * 100).toInt().coerceIn(0, 100)

        binding.sliderGru.value = gruPct.toFloat()
        binding.sliderTech.value = techPct.toFloat()
        binding.sliderFund.value = fundPct.toFloat()

        binding.tvGruWeightVal.text = "$gruPct%"
        binding.tvTechWeightVal.text = "$techPct%"
        binding.tvFundWeightVal.text = "$fundPct%"
        updateTotalWeight()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
