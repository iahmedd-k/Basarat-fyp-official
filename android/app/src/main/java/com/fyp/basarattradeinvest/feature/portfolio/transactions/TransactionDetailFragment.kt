package com.fyp.basarattradeinvest.feature.portfolio.transactions

import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentTransactionDetailBinding
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import com.fyp.basarattradeinvest.feature.portfolio.transactions.dialog.AddEditTransactionDialogFragment
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.util.Locale

class TransactionDetailFragment : Fragment() {

    companion object {
        const val PORTFOLIO_CHANGED_KEY = "portfolio_changed"
    }

    private var _binding: FragmentTransactionDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: TransactionDetailViewModel by viewModels { TransactionDetailViewModel.Factory() }
    private var transactionId: String = ""
    private var currentTransaction: PortfolioTransaction? = null

    private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        transactionId = arguments?.getString("transaction_id").orEmpty()
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentTransactionDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupListeners()
        observeState()

        if (transactionId.isNotBlank()) {
            viewModel.loadTransaction(transactionId)
        }
    }

    private fun setupListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.btnEditTransaction.setOnClickListener {
            val tx = currentTransaction ?: return@setOnClickListener
            val dialog = AddEditTransactionDialogFragment.newInstanceForEdit(
                txId = tx.id,
                symbol = tx.symbol,
                type = tx.transactionType,
                qty = tx.quantity,
                price = tx.price,
                fee = tx.fee,
                date = tx.transactionDate
            )
            dialog.onTransactionSaved = {
                findNavController().previousBackStackEntry?.savedStateHandle?.set(PORTFOLIO_CHANGED_KEY, true)
                viewModel.loadTransaction(transactionId)
            }
            dialog.show(childFragmentManager, "edit_transaction")
        }

        binding.btnDeleteTransaction.setOnClickListener {
            MaterialAlertDialogBuilder(requireContext())
                .setTitle("Delete Transaction?")
                .setMessage("Deleting this transaction will permanently remove it from your records and may affect your portfolio calculations.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Delete") { _, _ ->
                    viewModel.deleteTransaction(transactionId)
                }
                .show()
        }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is TransactionDetailUiState.Loading -> {
                            binding.progressLoading.visibility = View.VISIBLE
                            setActionButtonsEnabled(false)
                        }
                        is TransactionDetailUiState.Deleting -> {
                            binding.progressLoading.visibility = View.VISIBLE
                            binding.btnDeleteTransaction.text = "Deleting…"
                            setActionButtonsEnabled(false)
                        }
                        is TransactionDetailUiState.Success -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.btnDeleteTransaction.text = "Delete"
                            setActionButtonsEnabled(true)
                            currentTransaction = state.transaction
                            renderTransaction(state.transaction)
                        }
                        is TransactionDetailUiState.Deleted -> {
                            binding.progressLoading.visibility = View.GONE
                            findNavController().previousBackStackEntry?.savedStateHandle?.set(PORTFOLIO_CHANGED_KEY, true)
                            Toast.makeText(requireContext(), "Transaction deleted successfully.", Toast.LENGTH_SHORT).show()
                            findNavController().popBackStack()
                        }
                        is TransactionDetailUiState.Error -> {
                            binding.progressLoading.visibility = View.GONE
                            binding.btnDeleteTransaction.text = "Delete"
                            setActionButtonsEnabled(true)
                            Toast.makeText(requireContext(), state.message, Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
        }
    }

    private fun setActionButtonsEnabled(enabled: Boolean) {
        binding.btnDeleteTransaction.isEnabled = enabled
        binding.btnEditTransaction.isEnabled = enabled
    }

    private fun renderTransaction(tx: PortfolioTransaction) {
        val isBuy = tx.transactionType.equals("BUY", ignoreCase = true)
        binding.tvDetailTypeBadge.text = if (isBuy) "BUY" else "SELL"
        if (isBuy) {
            binding.tvDetailTypeBadge.setBackgroundResource(R.drawable.bg_badge_buy)
            binding.tvDetailTypeBadge.setTextColor(Color.parseColor("#18B981"))
        } else {
            binding.tvDetailTypeBadge.setBackgroundResource(R.drawable.bg_badge_sell)
            binding.tvDetailTypeBadge.setTextColor(Color.parseColor("#EF4444"))
        }

        binding.tvDetailSymbol.text = tx.symbol

        val total = tx.quantity * tx.price
        binding.tvDetailTotal.text = "PKR ${currencyFormat.format(total)}"
        binding.tvDetailSubtotal.text = "${if (isBuy) "Total amount invested" else "Total proceeds from sale"}"

        binding.tvDetailQuantity.text = String.format(Locale.US, "%.0f Shares", tx.quantity)
        binding.tvDetailPrice.text = "PKR ${currencyFormat.format(tx.price)}"
        binding.tvDetailFee.text = "PKR ${currencyFormat.format(tx.fee)}"
        binding.tvDetailDate.text = tx.transactionDate
        binding.tvDetailTxId.text = "ID: ${tx.id} • Created: ${tx.createdAt}"
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
