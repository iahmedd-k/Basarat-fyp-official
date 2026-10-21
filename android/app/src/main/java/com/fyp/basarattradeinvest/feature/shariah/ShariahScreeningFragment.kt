package com.fyp.basarattradeinvest.feature.shariah

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentShariahScreeningBinding
import com.fyp.basarattradeinvest.domain.model.shariah.ShariahStock
import com.fyp.basarattradeinvest.feature.shariah.adapter.ShariahStockAdapter
import kotlinx.coroutines.launch

class ShariahScreeningFragment : Fragment() {

    private var _binding: FragmentShariahScreeningBinding? = null
    private val binding get() = _binding!!

    private val viewModel: ShariahScreeningViewModel by activityViewModels()

    private var currentSortColumn: String? = null
    private var isSortAscending: Boolean = true
    private var rawStockList: List<ShariahStock> = emptyList()

    private val stockAdapter by lazy {
        ShariahStockAdapter { stock ->
            val sheet = com.fyp.basarattradeinvest.feature.shariah.details.StockShariahDetailsBottomSheet.newInstance(stock.symbol)
            sheet.show(childFragmentManager, "StockShariahDetailsBottomSheet")
        }
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentShariahScreeningBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerView()
        setupListeners()
        setupSortingHeaders()
        observeUiState()
    }

    override fun onStart() {
        super.onStart()
        viewModel.setLiveUpdatesActive(true)
    }

    override fun onStop() {
        viewModel.setLiveUpdatesActive(false)
        super.onStop()
    }

    private fun setupRecyclerView() {
        binding.rvShariahStocks.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = stockAdapter
        }
    }

    private fun setupListeners() {
        // Back
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        // Help
        binding.ivHelp.setOnClickListener {
            Toast.makeText(
                requireContext(),
                "PSX Shariah screening adheres to KMI methodology: interest-bearing debt < 37%, non-compliant investments < 33%, and purification of non-compliant income.",
                Toast.LENGTH_LONG
            ).show()
        }

        // Search Toggle
        binding.ivSearch.setOnClickListener {
            if (binding.layoutSearchBar.visibility == View.VISIBLE) {
                binding.layoutSearchBar.visibility = View.GONE
                binding.etSearch.setText("")
            } else {
                binding.layoutSearchBar.visibility = View.VISIBLE
                binding.etSearch.requestFocus()
            }
        }

        binding.ivSearchClear.setOnClickListener {
            binding.etSearch.setText("")
        }

        binding.etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                viewModel.onSearchQueryChanged(s?.toString().orEmpty())
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        // PSX Filter Pills
        binding.chipAllStocks.setOnClickListener {
            viewModel.setCategory("All Stocks")
        }

        binding.chipKmi30.setOnClickListener {
            viewModel.setCategory("KMI-30")
        }

        // Retry
        binding.btnRetry.setOnClickListener {
            viewModel.loadStocks()
        }
    }

    private fun setupSortingHeaders() {
        binding.thSymbol.setOnClickListener {
            toggleSort("symbol")
        }
        binding.thPrice.setOnClickListener {
            toggleSort("price")
        }
        binding.thChange.setOnClickListener {
            toggleSort("change")
        }
        binding.thPurification.setOnClickListener {
            toggleSort("purification")
        }
    }

    private fun toggleSort(column: String) {
        if (currentSortColumn == column) {
            isSortAscending = !isSortAscending
        } else {
            currentSortColumn = column
            isSortAscending = false
        }
        applyCurrentSort()
    }

    private fun applyCurrentSort() {
        if (rawStockList.isEmpty()) return

        val sorted = when (currentSortColumn) {
            "symbol" -> if (isSortAscending) rawStockList.sortedBy { it.symbol } else rawStockList.sortedByDescending { it.symbol }
            "price" -> if (isSortAscending) rawStockList.sortedBy { it.price } else rawStockList.sortedByDescending { it.price }
            "change" -> if (isSortAscending) rawStockList.sortedBy { it.changePercent } else rawStockList.sortedByDescending { it.changePercent }
            "purification" -> if (isSortAscending) rawStockList.sortedBy { it.purificationRate } else rawStockList.sortedByDescending { it.purificationRate }
            else -> rawStockList
        }
        stockAdapter.submitList(sorted)
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is ShariahScreeningUiState.Loading -> {
                            binding.progressLoading.visibility = View.VISIBLE
                            binding.rvShariahStocks.visibility = View.GONE
                            binding.layoutEmptyState.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.GONE
                        }
                        is ShariahScreeningUiState.Success -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.rvShariahStocks.visibility = View.VISIBLE
                            binding.layoutEmptyState.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.GONE

                            rawStockList = state.stocks
                            applyCurrentSort()

                            updateFilterChips(state.category)
                        }
                        is ShariahScreeningUiState.Empty -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.rvShariahStocks.visibility = View.GONE
                            binding.layoutEmptyState.visibility = View.VISIBLE
                            binding.layoutErrorState.visibility = View.GONE
                        }
                        is ShariahScreeningUiState.Error -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.rvShariahStocks.visibility = View.GONE
                            binding.layoutEmptyState.visibility = View.GONE
                            binding.layoutErrorState.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun updateFilterChips(activeCategory: String) {
        val chips = listOf(
            binding.chipAllStocks to "All Stocks",
            binding.chipKmi30 to "KMI-30"
        )

        chips.forEach { (view, category) ->
            val isSelected = activeCategory.equals(category, ignoreCase = true)
            if (isSelected) {
                view.setBackgroundResource(R.drawable.bg_chip_filter_selected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))
            } else {
                view.setBackgroundResource(R.drawable.bg_chip_filter_unselected)
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
            }
        }

        // Only KMI-30 ships as a bulk compliance list, so the whole-board view must not claim
        // its rows are already screened.
        binding.tvTopSubtitle.text = if (activeCategory.equals("KMI-30", ignoreCase = true)) {
            "PSX KMI-30 Shariah index"
        } else {
            "All PSX stocks — tap one to screen it"
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
