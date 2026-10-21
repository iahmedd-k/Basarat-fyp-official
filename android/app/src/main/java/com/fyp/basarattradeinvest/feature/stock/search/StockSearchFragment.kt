package com.fyp.basarattradeinvest.feature.stock.search

import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import androidx.core.widget.doAfterTextChanged
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentStockSearchBinding
import kotlinx.coroutines.launch

class StockSearchFragment : Fragment() {

    private var _binding: FragmentStockSearchBinding? = null
    private val binding get() = _binding!!

    private val viewModel: StockSearchViewModel by viewModels()
    private lateinit var adapter: StockSearchAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentStockSearchBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerView()
        setupListeners()
        observeUiState()

        // Focus search edit text and show keyboard
        binding.etSearchQuery.requestFocus()
        val imm = requireContext().getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager
        imm?.showSoftInput(binding.etSearchQuery, InputMethodManager.SHOW_IMPLICIT)
    }

    private fun setupRecyclerView() {
        adapter = StockSearchAdapter { item ->
            // Hide keyboard before navigating
            val imm = requireContext().getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager
            imm?.hideSoftInputFromWindow(binding.etSearchQuery.windowToken, 0)

            // Navigate to StockDetailFragment with selected symbol
            val bundle = Bundle().apply {
                putString("symbol", item.symbol)
            }
            findNavController().navigate(R.id.action_stockSearch_to_stockDetail, bundle)
        }

        binding.rvSearchResults.layoutManager = LinearLayoutManager(requireContext())
        binding.rvSearchResults.adapter = adapter
    }

    private fun setupListeners() {
        binding.ivBack.setOnClickListener {
            val imm = requireContext().getSystemService(Context.INPUT_METHOD_SERVICE) as? InputMethodManager
            imm?.hideSoftInputFromWindow(binding.etSearchQuery.windowToken, 0)
            findNavController().popBackStack()
        }

        binding.ivClearQuery.setOnClickListener {
            binding.etSearchQuery.text?.clear()
        }

        binding.btnRetry.setOnClickListener {
            viewModel.retry()
        }

        binding.etSearchQuery.doAfterTextChanged { text ->
            val q = text?.toString().orEmpty()
            binding.ivClearQuery.visibility = if (q.isNotEmpty()) View.VISIBLE else View.GONE
            viewModel.onQueryChanged(q)
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

    private fun renderUiState(state: StockSearchUiState) {
        binding.layoutLoading.visibility = View.GONE
        binding.layoutIdle.visibility = View.GONE
        binding.layoutEmpty.visibility = View.GONE
        binding.layoutError.visibility = View.GONE
        binding.rvSearchResults.visibility = View.GONE

        when (state) {
            is StockSearchUiState.Idle -> {
                binding.layoutIdle.visibility = View.VISIBLE
            }
            is StockSearchUiState.Loading -> {
                binding.layoutLoading.visibility = View.VISIBLE
            }
            is StockSearchUiState.Success -> {
                binding.rvSearchResults.visibility = View.VISIBLE
                adapter.submitList(state.results)
            }
            is StockSearchUiState.Empty -> {
                binding.layoutEmpty.visibility = View.VISIBLE
                binding.tvEmptyMessage.text = "No stocks found matching \"${state.query}\""
            }
            is StockSearchUiState.Error -> {
                binding.layoutError.visibility = View.VISIBLE
                binding.tvErrorMessage.text = state.message
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
