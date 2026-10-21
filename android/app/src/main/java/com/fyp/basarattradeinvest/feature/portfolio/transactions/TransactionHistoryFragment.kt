package com.fyp.basarattradeinvest.feature.portfolio.transactions

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentTransactionHistoryBinding
import com.fyp.basarattradeinvest.domain.model.portfolio.TransactionListPage
import com.fyp.basarattradeinvest.feature.portfolio.transactions.adapter.TransactionAdapter
import com.fyp.basarattradeinvest.feature.portfolio.transactions.dialog.AddEditTransactionDialogFragment
import com.fyp.basarattradeinvest.feature.portfolio.transactions.dialog.RecordCompletedTradeDialogFragment
import kotlinx.coroutines.launch

class TransactionHistoryFragment : Fragment() {

    private var _binding: FragmentTransactionHistoryBinding? = null
    private val binding get() = _binding!!

    private val viewModel: TransactionHistoryViewModel by viewModels { TransactionHistoryViewModel.Factory() }
    private lateinit var adapter: TransactionAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentTransactionHistoryBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerView()
        setupListeners()
        observeState()
    }

    override fun onResume() {
        super.onResume()
        val handle = findNavController().currentBackStackEntry?.savedStateHandle ?: return
        if (handle.get<Boolean>(TransactionDetailFragment.PORTFOLIO_CHANGED_KEY) == true) {
            handle.remove<Boolean>(TransactionDetailFragment.PORTFOLIO_CHANGED_KEY)
            viewModel.loadTransactions()
        }
    }

    private fun setupRecyclerView() {
        adapter = TransactionAdapter { txId ->
            val bundle = bundleOf("transaction_id" to txId)
            findNavController().navigate(R.id.action_transactionHistory_to_transactionDetail, bundle)
        }
        binding.rvTransactions.layoutManager = LinearLayoutManager(requireContext())
        binding.rvTransactions.adapter = adapter
    }

    private fun setupListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.btnNewTransaction.setOnClickListener {
            val dialog = AddEditTransactionDialogFragment.newInstanceForCreate()
            dialog.onTransactionSaved = {
                viewModel.loadTransactions()
            }
            dialog.show(childFragmentManager, "add_transaction")
        }

        binding.btnRecordTrade.setOnClickListener {
            val dialog = RecordCompletedTradeDialogFragment()
            dialog.onTradeRecorded = {
                viewModel.loadTransactions()
            }
            dialog.show(childFragmentManager, "record_trade")
        }

        binding.chipTypeAll.setOnClickListener {
            updateFilterChips(null)
            viewModel.setFilterType(null)
        }

        binding.chipTypeBuy.setOnClickListener {
            updateFilterChips("BUY")
            viewModel.setFilterType("BUY")
        }

        binding.chipTypeSell.setOnClickListener {
            updateFilterChips("SELL")
            viewModel.setFilterType("SELL")
        }
    }

    private fun updateFilterChips(selected: String?) {
        binding.chipTypeAll.setBackgroundResource(if (selected == null) R.drawable.bg_tab_selected else R.drawable.bg_tab_unselected)
        binding.chipTypeAll.setTextColor(if (selected == null) Color.WHITE else Color.parseColor("#667085"))

        binding.chipTypeBuy.setBackgroundResource(if (selected == "BUY") R.drawable.bg_tab_selected else R.drawable.bg_tab_unselected)
        binding.chipTypeBuy.setTextColor(if (selected == "BUY") Color.WHITE else Color.parseColor("#667085"))

        binding.chipTypeSell.setBackgroundResource(if (selected == "SELL") R.drawable.bg_tab_selected else R.drawable.bg_tab_unselected)
        binding.chipTypeSell.setTextColor(if (selected == "SELL") Color.WHITE else Color.parseColor("#667085"))
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is TransactionHistoryUiState.Loading -> {
                            binding.progressLoading.visibility = View.VISIBLE
                            binding.layoutEmpty.visibility = View.GONE
                        }
                        is TransactionHistoryUiState.Success -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.rvTransactions.visibility = View.VISIBLE
                            binding.tvTotalCount.text = "Showing ${state.page.items.size} of ${state.page.total} transactions"
                            adapter.submitList(state.page.items)
                        }
                        is TransactionHistoryUiState.Empty -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.rvTransactions.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.VISIBLE
                            binding.tvTotalCount.text = "0 transactions"
                        }
                        is TransactionHistoryUiState.Error -> {
                            binding.progressLoading.visibility = View.GONE
                            Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
