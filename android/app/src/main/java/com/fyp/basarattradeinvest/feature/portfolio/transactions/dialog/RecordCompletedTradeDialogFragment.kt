package com.fyp.basarattradeinvest.feature.portfolio.transactions.dialog

import android.app.Dialog
import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.Window
import android.widget.Toast
import androidx.core.widget.doAfterTextChanged
import androidx.fragment.app.DialogFragment
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.data.repository.PortfolioRepositoryImpl
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.databinding.DialogRecordCompletedTradeBinding
import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult
import com.fyp.basarattradeinvest.domain.usecase.portfolio.RecordCompletedTradeUseCase
import com.fyp.basarattradeinvest.feature.stock.search.StockSearchAdapter
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class RecordCompletedTradeDialogFragment : DialogFragment() {

    private var _binding: DialogRecordCompletedTradeBinding? = null
    private val binding get() = _binding!!

    private val recordTradeUseCase = RecordCompletedTradeUseCase(PortfolioRepositoryImpl())
    private val stockRepository = StockRepositoryImpl()

    private lateinit var suggestionAdapter: StockSearchAdapter
    private var verifiedSelectedStock: StockSearchResult? = null
    private var searchJob: Job? = null
    private var isSubmitting = false

    var onTradeRecorded: (() -> Unit)? = null

    private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        val dialog = super.onCreateDialog(savedInstanceState)
        dialog.window?.requestFeature(Window.FEATURE_NO_TITLE)
        return dialog
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = DialogRecordCompletedTradeBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onStart() {
        super.onStart()
        dialog?.window?.setLayout(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val today = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
        binding.etBuyDate.setText(today)
        binding.etSellDate.setText(today)

        setupSearchAndSuggestions()
        setupListeners()
    }

    private fun setupSearchAndSuggestions() {
        suggestionAdapter = StockSearchAdapter { stock ->
            selectStock(stock)
        }
        binding.rvTradeStockSuggestions.layoutManager = LinearLayoutManager(requireContext())
        binding.rvTradeStockSuggestions.adapter = suggestionAdapter

        binding.etTradeStockSearch.doAfterTextChanged { text ->
            val query = text?.toString()?.trim() ?: ""
            searchJob?.cancel()
            if (query.isEmpty()) {
                binding.rvTradeStockSuggestions.visibility = View.GONE
                binding.layoutTradeQuickChips.visibility = View.VISIBLE
            } else {
                searchJob = lifecycleScope.launch {
                    delay(250)
                    val result = stockRepository.searchStocks(query, limit = 6)
                    if (result.isSuccess) {
                        val list = result.getOrDefault(emptyList())
                        if (list.isNotEmpty()) {
                            binding.layoutTradeQuickChips.visibility = View.GONE
                            binding.rvTradeStockSuggestions.visibility = View.VISIBLE
                            suggestionAdapter.submitList(list)
                        } else {
                            binding.rvTradeStockSuggestions.visibility = View.GONE
                            binding.layoutTradeQuickChips.visibility = View.VISIBLE
                        }
                    }
                }
            }
        }

        binding.chipTradeLuck.setOnClickListener { selectQuickSymbol("LUCK") }
        binding.chipTradeOgdc.setOnClickListener { selectQuickSymbol("OGDC") }
        binding.chipTradeSys.setOnClickListener { selectQuickSymbol("SYS") }
        binding.chipTradeHubc.setOnClickListener { selectQuickSymbol("HUBC") }
        binding.chipTradeEngro.setOnClickListener { selectQuickSymbol("ENGRO") }
        binding.chipTradeMebl.setOnClickListener { selectQuickSymbol("MEBL") }

        binding.btnTradeChangeStock.setOnClickListener {
            clearSelectedStock()
        }
    }

    private fun selectQuickSymbol(symbol: String) {
        lifecycleScope.launch {
            val overviewResult = stockRepository.getStockOverview(symbol)
            if (overviewResult.isSuccess) {
                val detail = overviewResult.getOrThrow()
                val stock = StockSearchResult(
                    symbol = detail.symbol,
                    name = detail.companyName,
                    sector = detail.sector
                )
                selectStock(stock, detail.price)
            } else {
                val stock = StockSearchResult(
                    symbol = symbol,
                    name = "$symbol Limited",
                    sector = "PSX Equities"
                )
                selectStock(stock)
            }
        }
    }

    private fun selectStock(stock: StockSearchResult, knownPrice: Double? = null) {
        verifiedSelectedStock = stock
        binding.tvTradeError.visibility = View.GONE

        binding.tilTradeStockSearch.visibility = View.GONE
        binding.layoutTradeQuickChips.visibility = View.GONE
        binding.rvTradeStockSuggestions.visibility = View.GONE

        binding.cardTradeSelectedStock.visibility = View.VISIBLE
        binding.tvTradeSelectedSymbol.text = stock.symbol
        binding.tvTradeSelectedName.text = stock.name
        binding.tvTradeSelectedSector.text = stock.sector
        binding.tvTradeSelectedLetter.text = stock.symbol.take(1).uppercase()

        if (knownPrice != null && knownPrice > 0.0) {
            binding.tvTradeSelectedLtp.text = "Market Price: PKR ${currencyFormat.format(knownPrice)}"
        } else {
            binding.tvTradeSelectedLtp.text = "Fetching live market price..."
            lifecycleScope.launch {
                val overview = stockRepository.getStockOverview(stock.symbol)
                if (overview.isSuccess) {
                    val price = overview.getOrThrow().price
                    binding.tvTradeSelectedLtp.text = "Market Price: PKR ${currencyFormat.format(price)}"
                } else {
                    binding.tvTradeSelectedLtp.text = "Live price unavailable on PSX feed"
                }
            }
        }
    }

    private fun clearSelectedStock() {
        verifiedSelectedStock = null
        binding.cardTradeSelectedStock.visibility = View.GONE
        binding.tilTradeStockSearch.visibility = View.VISIBLE
        binding.layoutTradeQuickChips.visibility = View.VISIBLE
        binding.rvTradeStockSuggestions.visibility = View.GONE
        binding.etTradeStockSearch.text?.clear()
    }

    private fun setupListeners() {
        binding.btnCancelTrade.setOnClickListener {
            dismiss()
        }

        binding.btnSubmitTrade.setOnClickListener {
            submitTrade()
        }
    }

    private fun submitTrade() {
        if (isSubmitting) return
        binding.tvTradeError.visibility = View.GONE

        val symbol = verifiedSelectedStock?.symbol.orEmpty()
        val qty = binding.etTradeQuantity.text?.toString()?.toDoubleOrNull()
        val buyPrice = binding.etBuyPrice.text?.toString()?.toDoubleOrNull()
        val buyDate = binding.etBuyDate.text?.toString()?.trim().orEmpty()
        val buyFee = binding.etBuyFee.text?.toString()?.toDoubleOrNull() ?: 0.0
        val sellPrice = binding.etSellPrice.text?.toString()?.toDoubleOrNull()
        val sellDate = binding.etSellDate.text?.toString()?.trim().orEmpty()
        val sellFee = binding.etSellFee.text?.toString()?.toDoubleOrNull() ?: 0.0

        if (symbol.isBlank()) {
            showError("Please search and select a verified PSX stock from the list.")
            return
        }
        if (qty == null || qty <= 0) {
            showError("Please enter valid traded shares.")
            return
        }
        if (buyPrice == null || buyPrice <= 0) {
            showError("Please enter a valid buy price.")
            return
        }
        if (buyDate.isBlank() || !buyDate.matches(Regex("^\\d{4}-\\d{2}-\\d{2}$"))) {
            showError("Buy date must be in YYYY-MM-DD format.")
            return
        }
        if (sellPrice == null || sellPrice <= 0) {
            showError("Please enter a valid sell price.")
            return
        }
        if (sellDate.isBlank() || !sellDate.matches(Regex("^\\d{4}-\\d{2}-\\d{2}$"))) {
            showError("Sell date must be in YYYY-MM-DD format.")
            return
        }

        isSubmitting = true
        binding.layoutRecordingTrade.visibility = View.VISIBLE
        binding.btnSubmitTrade.text = "Recording…"
        binding.btnSubmitTrade.isEnabled = false
        binding.btnCancelTrade.isEnabled = false

        lifecycleScope.launch {
            val result = recordTradeUseCase(
                symbol = symbol,
                quantity = qty,
                buyPrice = buyPrice,
                buyDate = buyDate,
                buyFee = buyFee,
                sellPrice = sellPrice,
                sellDate = sellDate,
                sellFee = sellFee
            )

            if (result.isSuccess) {
                val trade = result.getOrThrow()
                Toast.makeText(requireContext(), "Completed trade recorded", Toast.LENGTH_SHORT).show()
                onTradeRecorded?.invoke()
                binding.layoutRecordingTrade.visibility = View.GONE

                binding.cardTradeResult.visibility = View.VISIBLE
                val prefix = if (trade.realizedPnl >= 0) "+" else ""
                binding.tvResultPnl.text = String.format(
                    Locale.US,
                    "Realized P&L: %sPKR %s (%.2f%%)",
                    prefix,
                    currencyFormat.format(trade.realizedPnl),
                    trade.realizedPnlPercent
                )
                if (trade.realizedPnl >= 0) {
                    binding.tvResultPnl.setTextColor(Color.parseColor("#18B981"))
                } else {
                    binding.tvResultPnl.setTextColor(Color.parseColor("#EF4444"))
                }
                binding.tvResultDetails.text = String.format(
                    Locale.US,
                    "Invested: PKR %s | Proceeds: PKR %s | Held: %d days",
                    currencyFormat.format(trade.totalInvested),
                    currencyFormat.format(trade.totalProceeds),
                    trade.holdingPeriodDays
                )

                binding.btnSubmitTrade.visibility = View.GONE
                binding.btnCancelTrade.text = "Close"
                binding.btnCancelTrade.isEnabled = true
            } else {
                isSubmitting = false
                binding.layoutRecordingTrade.visibility = View.GONE
                binding.btnSubmitTrade.text = "Record Trade"
                binding.btnSubmitTrade.isEnabled = true
                binding.btnCancelTrade.isEnabled = true
                showError(result.exceptionOrNull()?.message ?: "Failed to record trade.")
            }
        }
    }

    private fun showError(msg: String) {
        binding.tvTradeError.text = msg
        binding.tvTradeError.visibility = View.VISIBLE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        searchJob?.cancel()
        _binding = null
    }
}
