package com.fyp.basarattradeinvest.feature.portfolio.holding

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.os.bundleOf
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentHoldingDetailBinding
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingDetail
import com.fyp.basarattradeinvest.feature.portfolio.transactions.adapter.TransactionAdapter
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

class HoldingDetailFragment : Fragment() {

    private var _binding: FragmentHoldingDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: HoldingDetailViewModel by activityViewModels { HoldingDetailViewModel.Factory() }
    private var symbol: String = "LUCK"
    private lateinit var transactionAdapter: TransactionAdapter

    private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        symbol = arguments?.getString("symbol") ?: "LUCK"
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentHoldingDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerView()
        setupListeners()
        observeState()

        if (viewModel.shouldLoadHolding(symbol)) {
            viewModel.loadHolding(symbol)
        }
    }

    private fun setupRecyclerView() {
        transactionAdapter = TransactionAdapter { txId ->
            val bundle = bundleOf("transaction_id" to txId)
            findNavController().navigate(R.id.action_holdingDetail_to_transactionDetail, bundle)
        }
        binding.rvHoldingTransactions.layoutManager = LinearLayoutManager(requireContext())
        binding.rvHoldingTransactions.adapter = transactionAdapter
    }

    private fun setupListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.btnNavStockDetail.setOnClickListener {
            val bundle = bundleOf("symbol" to symbol)
            findNavController().navigate(R.id.action_holdingDetail_to_stockDetail, bundle)
        }

        binding.btnNavForecast.setOnClickListener {
            val bundle = bundleOf("symbol" to symbol)
            findNavController().navigate(R.id.action_holdingDetail_to_stockAnalysis, bundle)
        }

        binding.btnNavRecommendation.setOnClickListener {
            val bundle = bundleOf("symbol" to symbol)
            findNavController().navigate(R.id.action_holdingDetail_to_stockRecommendationDetail, bundle)
        }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is HoldingDetailUiState.Loading -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.layoutHoldingSkeleton.visibility = View.VISIBLE
                        }
                        is HoldingDetailUiState.Success -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.layoutHoldingSkeleton.visibility = View.GONE
                            renderDetail(state.detail)
                        }
                        is HoldingDetailUiState.Error -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.layoutHoldingSkeleton.visibility = View.GONE
                            Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
        }
    }

    private fun renderDetail(detail: HoldingDetail) {
        binding.tvHoldingSymbol.text = detail.symbol
        val company = if (detail.companyName.isNotBlank() && detail.companyName != detail.symbol) {
            "${detail.companyName} • ${detail.sector}"
        } else {
            detail.sector
        }
        binding.tvHoldingCompanySector.text = company

        val weight = detail.portfolioWeight ?: 0.0
        binding.tvHoldingWeightBadge.text = String.format(Locale.US, "%.1f%% Weight", weight)

        val curPrice = detail.currentPrice ?: detail.averageCost
        val marketVal = detail.marketValue ?: (detail.quantity * curPrice)
        binding.tvDetailMarketValue.text = "PKR ${currencyFormat.format(marketVal)}"

        val pnl = detail.unrealizedPnl ?: 0.0
        val pnlPct = detail.unrealizedPnlPercent ?: 0.0
        val prefix = if (pnl >= 0) "+" else ""
        binding.tvDetailUnrealizedPnl.text = String.format(
            Locale.US,
            "%sPKR %s (%.2f%%)",
            prefix,
            currencyFormat.format(pnl),
            pnlPct
        )
        if (pnl >= 0) {
            binding.tvDetailUnrealizedPnl.setTextColor(Color.parseColor("#18B981"))
        } else {
            binding.tvDetailUnrealizedPnl.setTextColor(Color.parseColor("#EF4444"))
        }

        binding.tvDetailInvestedValue.text = "PKR ${currencyFormat.format(detail.investedValue)}"
        binding.tvDetailRealizedPnl.text = "PKR ${currencyFormat.format(detail.realizedPnl)}"

        binding.tvDetailShares.text = String.format(Locale.US, "%.0f", detail.quantity)
        binding.tvDetailAvgCost.text = "PKR ${currencyFormat.format(detail.averageCost)}"
        binding.tvDetailCurrentPrice.text = "PKR ${currencyFormat.format(curPrice)}"

        val updateText = if (detail.priceUpdatedAt != null) "Updated: ${detail.priceUpdatedAt}" else "Available"
        binding.tvDetailPriceUpdated.text = "Status: ${detail.priceStatus} • $updateText"

        if (detail.transactions.isEmpty()) {
            binding.tvEmptyTransactions.visibility = View.VISIBLE
            binding.rvHoldingTransactions.visibility = View.GONE
        } else {
            binding.tvEmptyTransactions.visibility = View.GONE
            binding.rvHoldingTransactions.visibility = View.VISIBLE
            transactionAdapter.submitList(detail.transactions)
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
