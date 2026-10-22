package com.fyp.basarattradeinvest.feature.shariah.details

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.BottomSheetStockShariahDetailsBinding
import com.fyp.basarattradeinvest.domain.model.shariah.DividendPurificationResult
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCompliance
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCriteria
import com.fyp.basarattradeinvest.feature.shariah.adapter.ShariahCriteriaAdapter
import com.google.android.material.bottomsheet.BottomSheetDialogFragment
import kotlinx.coroutines.launch
import java.util.Locale

class StockShariahDetailsBottomSheet : BottomSheetDialogFragment() {

    private var _binding: BottomSheetStockShariahDetailsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: StockShariahDetailsViewModel by viewModels()
    private val criteriaAdapter by lazy { ShariahCriteriaAdapter() }

    private var stockSymbol: String = "LUCK"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        stockSymbol = arguments?.getString(ARG_SYMBOL) ?: "LUCK"
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = BottomSheetStockShariahDetailsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerView()
        setupListeners()
        observeViewModel()

        viewModel.loadStockShariah(stockSymbol)
    }

    private fun setupRecyclerView() {
        binding.rvShariahCriteria.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = criteriaAdapter
            isNestedScrollingEnabled = false
        }
    }

    private fun setupListeners() {
        binding.ivCloseSheet.setOnClickListener {
            dismiss()
        }

        binding.tabCriteria.setOnClickListener {
            showCriteriaSection()
        }

        binding.tabPurification.setOnClickListener {
            showPurificationSection()
        }

        binding.btnCalculatePurification.setOnClickListener {
            val income = binding.etDividendIncome.text?.toString()?.trim()?.toDoubleOrNull()

            if (income == null || income <= 0.0) {
                Toast.makeText(requireContext(), "Please enter a dividend income greater than zero", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            viewModel.calculatePurification(stockSymbol, income)
        }
    }

    private fun showCriteriaSection() {
        binding.tabCriteria.setBackgroundResource(R.drawable.bg_chip_filter_selected)
        binding.tabCriteria.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))

        binding.tabPurification.setBackgroundResource(R.drawable.bg_chip_filter_unselected)
        binding.tabPurification.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))

        binding.containerCriteriaSection.visibility = View.VISIBLE
        binding.containerPurificationSection.visibility = View.GONE
    }

    private fun showPurificationSection() {
        binding.tabPurification.setBackgroundResource(R.drawable.bg_chip_filter_selected)
        binding.tabPurification.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))

        binding.tabCriteria.setBackgroundResource(R.drawable.bg_chip_filter_unselected)
        binding.tabCriteria.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))

        binding.containerCriteriaSection.visibility = View.GONE
        binding.containerPurificationSection.visibility = View.VISIBLE
    }

    private fun observeViewModel() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    viewModel.complianceState.collect { state ->
                        when (state) {
                            is StockShariahComplianceUiState.Loading -> {
                                // Keep existing content or show light loading
                            }
                            is StockShariahComplianceUiState.Success -> {
                                bindComplianceHeader(state.compliance)
                            }
                            is StockShariahComplianceUiState.Error -> {
                                binding.tvShariahBadge.text = "Screening unavailable"
                                binding.tvShariahBadge.setBackgroundResource(R.drawable.bg_badge_shariah_non_compliant)
                                binding.tvShariahBadge.setTextColor(
                                    ContextCompat.getColor(requireContext(), R.color.color_text_secondary)
                                )
                                binding.tvShariahMethod.text = "—"
                                binding.tvShariahScore.text = "—"
                                binding.tvComplianceSummary.text = state.message
                            }
                        }
                    }
                }

                launch {
                    viewModel.criteriaState.collect { state ->
                        when (state) {
                            is StockShariahCriteriaUiState.Loading -> {
                                binding.progressCriteria.visibility = View.VISIBLE
                                binding.tvCriteriaStatus.visibility = View.GONE
                            }
                            is StockShariahCriteriaUiState.Success -> {
                                binding.progressCriteria.visibility = View.GONE
                                bindCriteriaList(state.criteria)
                            }
                            is StockShariahCriteriaUiState.Error -> {
                                binding.progressCriteria.visibility = View.GONE
                                criteriaAdapter.submitList(emptyList())
                                binding.tabCriteria.text = "Screening Criteria"
                                showCriteriaStatus(state.message)
                            }
                        }
                    }
                }

                launch {
                    viewModel.purificationState.collect { state ->
                        when (state) {
                            is PurificationCalculationUiState.Idle -> {
                                binding.progressPurification.visibility = View.GONE
                                binding.cardPurificationResult.visibility = View.GONE
                                binding.tvPurificationError.visibility = View.GONE
                            }
                            is PurificationCalculationUiState.Calculating -> {
                                binding.progressPurification.visibility = View.VISIBLE
                                binding.cardPurificationResult.visibility = View.GONE
                                binding.tvPurificationError.visibility = View.GONE
                            }
                            is PurificationCalculationUiState.Success -> {
                                binding.progressPurification.visibility = View.GONE
                                binding.tvPurificationError.visibility = View.GONE
                                bindPurificationResult(state.result)
                            }
                            is PurificationCalculationUiState.Error -> {
                                binding.progressPurification.visibility = View.GONE
                                binding.cardPurificationResult.visibility = View.GONE
                                binding.tvPurificationError.visibility = View.VISIBLE
                                binding.tvPurificationError.text = state.message
                            }
                        }
                    }
                }
            }
        }
    }

    private fun bindComplianceHeader(item: StockShariahCompliance) {
        val context = requireContext()
        binding.tvShariahSymbol.text = item.symbol
        binding.tvShariahSector.text = item.sector?.let { "$it • PSX" } ?: "PSX"
        binding.tvShariahMethod.text = item.screeningMethod ?: "—"

        binding.tvShariahScore.text = item.overallScore?.let {
            String.format(Locale.US, "%.1f / 100", it)
        } ?: "—"

        when {
            !item.screeningAvailable -> {
                binding.tvShariahBadge.text = "Not screened"
                binding.tvShariahBadge.setBackgroundResource(R.drawable.bg_badge_shariah_non_compliant)
                binding.tvShariahBadge.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
            }
            item.isCompliant -> {
                binding.tvShariahBadge.text = "KMI-30 Compliant ✓"
                binding.tvShariahBadge.setBackgroundResource(R.drawable.bg_badge_shariah_compliant)
                binding.tvShariahBadge.setTextColor(ContextCompat.getColor(context, R.color.color_shariah_teal))
            }
            else -> {
                binding.tvShariahBadge.text = "Non-Compliant ✗"
                binding.tvShariahBadge.setBackgroundResource(R.drawable.bg_badge_shariah_non_compliant)
                binding.tvShariahBadge.setTextColor(ContextCompat.getColor(context, R.color.color_negative))
            }
        }

        val summary = item.complianceSummary?.takeIf { it.isNotBlank() }
        binding.tvComplianceSummary.visibility = if (summary == null) View.GONE else View.VISIBLE
        binding.tvComplianceSummary.text = summary.orEmpty()
    }

    private fun showCriteriaStatus(message: String) {
        binding.tvCriteriaStatus.visibility = View.VISIBLE
        binding.tvCriteriaStatus.text = message
    }

    private fun bindCriteriaList(item: StockShariahCriteria) {
        criteriaAdapter.submitList(item.criteria)
        binding.tabCriteria.text = "Screening Criteria (${item.criteria.size})"
        if (item.criteria.isEmpty()) {
            showCriteriaStatus(
                if (item.screeningAvailable) {
                    "No screening criteria published for this symbol."
                } else {
                    "This symbol is not covered by the PSX KMI-30 screening."
                }
            )
        } else {
            binding.tvCriteriaStatus.visibility = View.GONE
        }
    }

    private fun bindPurificationResult(result: DividendPurificationResult) {
        binding.cardPurificationResult.visibility = View.VISIBLE
        binding.tvPurificationAmount.text = String.format(Locale.US, "PKR %,.2f", result.purificationAmount)
        binding.tvPurificationRate.text = String.format(Locale.US, "%.2f%%", result.purificationRate * 100)

        val notes = result.notes?.takeIf { it.isNotBlank() }
        binding.tvPurificationNotes.visibility = if (notes == null) View.GONE else View.VISIBLE
        binding.tvPurificationNotes.text = notes.orEmpty()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    companion object {
        private const val ARG_SYMBOL = "arg_symbol"

        fun newInstance(symbol: String): StockShariahDetailsBottomSheet {
            return StockShariahDetailsBottomSheet().apply {
                arguments = Bundle().apply {
                    putString(ARG_SYMBOL, symbol)
                }
            }
        }
    }
}
