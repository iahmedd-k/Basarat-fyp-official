package com.fyp.basarattradeinvest.feature.profile

import android.content.res.ColorStateList
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentRiskProfileBinding
import com.fyp.basarattradeinvest.domain.model.auth.InvestmentProfileOptions
import com.fyp.basarattradeinvest.domain.model.auth.UserProfile
import com.fyp.basarattradeinvest.feature.auth.AuthUiState
import com.google.android.material.chip.Chip
import kotlinx.coroutines.launch
import java.util.Locale

class RiskProfileFragment : Fragment() {

    private var _binding: FragmentRiskProfileBinding? = null
    private val binding get() = _binding!!

    private val viewModel: RiskProfileViewModel by viewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentRiskProfileBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupClickListeners()
        observeData()
    }

    private fun setupClickListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnRetry.setOnClickListener {
            viewModel.loadData()
        }

        binding.btnSavePreferences.setOnClickListener {
            val selectedRiskTolerance = getSelectedChipTag(binding.cgRiskTolerance)
            val selectedInvestmentHorizon = getSelectedChipTag(binding.cgInvestmentHorizon)
            val selectedSectors = getSelectedChipTags(binding.cgSectors)

            viewModel.savePreferences(
                riskTolerance = selectedRiskTolerance,
                investmentHorizon = selectedInvestmentHorizon,
                selectedSectors = selectedSectors
            )
        }
    }

    private fun observeData() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                // Collect Options & Current Profile State
                launch {
                    viewModel.uiState.collect { state ->
                        when (state) {
                            is RiskProfileUiState.Loading -> {
                                binding.pbInitialLoading.visibility = View.VISIBLE
                                binding.layoutContent.visibility = View.GONE
                                binding.layoutError.visibility = View.GONE
                            }
                            is RiskProfileUiState.Success -> {
                                binding.pbInitialLoading.visibility = View.GONE
                                binding.layoutError.visibility = View.GONE
                                binding.layoutContent.visibility = View.VISIBLE
                                populateDynamicOptions(state.options, state.currentProfile)
                            }
                            is RiskProfileUiState.Error -> {
                                binding.pbInitialLoading.visibility = View.GONE
                                binding.layoutContent.visibility = View.GONE
                                binding.layoutError.visibility = View.VISIBLE
                                binding.tvErrorMessage.text = state.message
                            }
                        }
                    }
                }

                // Collect Save Submission State
                launch {
                    viewModel.saveUiState.collect { state ->
                        when (state) {
                            is AuthUiState.Idle -> {
                                binding.pbSaving.visibility = View.GONE
                                binding.tvSaveLabel.visibility = View.VISIBLE
                                binding.btnSavePreferences.isEnabled = true
                            }
                            is AuthUiState.Loading -> {
                                binding.pbSaving.visibility = View.VISIBLE
                                binding.tvSaveLabel.visibility = View.GONE
                                binding.btnSavePreferences.isEnabled = false
                            }
                            is AuthUiState.Success -> {
                                binding.pbSaving.visibility = View.GONE
                                binding.tvSaveLabel.visibility = View.VISIBLE
                                binding.btnSavePreferences.isEnabled = true
                                Toast.makeText(
                                    requireContext(),
                                    state.message ?: "Preferences saved successfully!",
                                    Toast.LENGTH_SHORT
                                ).show()
                                viewModel.resetSaveState()
                                findNavController().navigateUp()
                            }
                            is AuthUiState.Error -> {
                                binding.pbSaving.visibility = View.GONE
                                binding.tvSaveLabel.visibility = View.VISIBLE
                                binding.btnSavePreferences.isEnabled = true
                                Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                                viewModel.resetSaveState()
                            }
                        }
                    }
                }
            }
        }
    }

    private fun populateDynamicOptions(
        options: InvestmentProfileOptions,
        currentProfile: UserProfile?
    ) {
        // 1. Risk Tolerance (single-select chips)
        binding.cgRiskTolerance.removeAllViews()
        options.riskTolerances.forEach { riskValue ->
            val chip = createThemedChip(
                displayLabel = riskValue.replace("_", " ").capitalizeWords(),
                backendTag = riskValue,
                isCheckable = true
            )
            binding.cgRiskTolerance.addView(chip)
            if (currentProfile?.riskTolerance.equals(riskValue, ignoreCase = true)) {
                chip.isChecked = true
            }
        }

        // 2. Investment Horizon (single-select chips)
        binding.cgInvestmentHorizon.removeAllViews()
        options.investmentHorizons.forEach { horizonValue ->
            val chip = createThemedChip(
                displayLabel = horizonValue.replace("_", " ").capitalizeWords(),
                backendTag = horizonValue,
                isCheckable = true
            )
            binding.cgInvestmentHorizon.addView(chip)
            if (currentProfile?.investmentHorizon.equals(horizonValue, ignoreCase = true)) {
                chip.isChecked = true
            }
        }

        // 3. Preferred Sectors (multi-select chips)
        binding.cgSectors.removeAllViews()
        val currentSectors = currentProfile?.sectorPreferences.orEmpty()
        options.sectors.forEach { sectorValue ->
            val chip = createThemedChip(
                displayLabel = sectorValue,
                backendTag = sectorValue,
                isCheckable = true
            )
            binding.cgSectors.addView(chip)
            if (currentSectors.contains(sectorValue)) {
                chip.isChecked = true
            }
        }
    }

    private fun createThemedChip(
        displayLabel: String,
        backendTag: String,
        isCheckable: Boolean
    ): Chip {
        val chip = Chip(requireContext())
        chip.text = displayLabel
        chip.tag = backendTag
        chip.isCheckable = isCheckable
        chip.isClickable = true

        val greenColor = ContextCompat.getColor(requireContext(), R.color.color_brand_primary)
        val surfaceColor = ContextCompat.getColor(requireContext(), R.color.color_surface)
        val textPrimary = ContextCompat.getColor(requireContext(), R.color.color_text_primary)
        val borderColor = ContextCompat.getColor(requireContext(), R.color.color_border)

        // Custom Chip colors matching BASARAT theme
        chip.chipBackgroundColor = ColorStateList(
            arrayOf(
                intArrayOf(android.R.attr.state_checked),
                intArrayOf()
            ),
            intArrayOf(
                ContextCompat.getColor(requireContext(), R.color.color_positive_bg),
                surfaceColor
            )
        )

        chip.chipStrokeColor = ColorStateList(
            arrayOf(
                intArrayOf(android.R.attr.state_checked),
                intArrayOf()
            ),
            intArrayOf(
                greenColor,
                borderColor
            )
        )
        chip.chipStrokeWidth = 2f

        chip.setTextColor(
            ColorStateList(
                arrayOf(
                    intArrayOf(android.R.attr.state_checked),
                    intArrayOf()
                ),
                intArrayOf(
                    greenColor,
                    textPrimary
                )
            )
        )

        return chip
    }

    private fun getSelectedChipTag(chipGroup: com.google.android.material.chip.ChipGroup): String? {
        val selectedId = chipGroup.checkedChipId
        if (selectedId == View.NO_ID) return null
        val chip = chipGroup.findViewById<Chip>(selectedId)
        return chip?.tag?.toString()
    }

    private fun getSelectedChipTags(chipGroup: com.google.android.material.chip.ChipGroup): List<String> {
        val result = mutableListOf<String>()
        for (i in 0 until chipGroup.childCount) {
            val child = chipGroup.getChildAt(i) as? Chip
            if (child != null && child.isChecked) {
                child.tag?.toString()?.let { result.add(it) }
            }
        }
        return result
    }

    private fun String.capitalizeWords(): String = split(" ").joinToString(" ") { word ->
        word.lowercase(Locale.ROOT).replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
