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
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.data.repository.PortfolioRepositoryImpl
import com.fyp.basarattradeinvest.data.repository.StockRepositoryImpl
import com.fyp.basarattradeinvest.databinding.DialogAddEditTransactionBinding
import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult
import com.fyp.basarattradeinvest.domain.usecase.portfolio.CreateTransactionUseCase
import com.fyp.basarattradeinvest.domain.usecase.portfolio.UpdateTransactionUseCase
import com.fyp.basarattradeinvest.feature.stock.search.StockSearchAdapter
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class AddEditTransactionDialogFragment : DialogFragment() {

    private var _binding: DialogAddEditTransactionBinding? = null
    private val binding get() = _binding!!

    private var isEditMode: Boolean = false
    private var transactionId: String? = null
    private var prefilledSymbol: String? = null
    private var selectedType: String = "BUY"

    private val createUseCase = CreateTransactionUseCase(PortfolioRepositoryImpl())
    private val updateUseCase = UpdateTransactionUseCase(PortfolioRepositoryImpl())
    private val stockRepository = StockRepositoryImpl()

    private lateinit var suggestionAdapter: StockSearchAdapter
    private var verifiedSelectedStock: StockSearchResult? = null
    private var searchJob: Job? = null
    private var isSubmitting = false
    private var submitButtonLabel = "Save"

    private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    var onTransactionSaved: (() -> Unit)? = null

    companion object {
        private const val ARG_IS_EDIT = "arg_is_edit"
        private const val ARG_TX_ID = "arg_tx_id"
        private const val ARG_SYMBOL = "arg_symbol"
        private const val ARG_QTY = "arg_qty"
        private const val ARG_PRICE = "arg_price"
        private const val ARG_FEE = "arg_fee"
        private const val ARG_DATE = "arg_date"
        private const val ARG_TYPE = "arg_type"

        fun newInstanceForCreate(prefilledSymbol: String? = null): AddEditTransactionDialogFragment {
            return AddEditTransactionDialogFragment().apply {
                arguments = Bundle().apply {
                    putBoolean(ARG_IS_EDIT, false)
                    putString(ARG_SYMBOL, prefilledSymbol)
                }
            }
        }

        fun newInstanceForEdit(
            txId: String,
            symbol: String,
            type: String,
            qty: Double,
            price: Double,
            fee: Double,
            date: String
        ): AddEditTransactionDialogFragment {
            return AddEditTransactionDialogFragment().apply {
                arguments = Bundle().apply {
                    putBoolean(ARG_IS_EDIT, true)
                    putString(ARG_TX_ID, txId)
                    putString(ARG_SYMBOL, symbol)
                    putString(ARG_TYPE, type)
                    putDouble(ARG_QTY, qty)
                    putDouble(ARG_PRICE, price)
                    putDouble(ARG_FEE, fee)
                    putString(ARG_DATE, date)
                }
            }
        }
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
        _binding = DialogAddEditTransactionBinding.inflate(inflater, container, false)
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

        isEditMode = arguments?.getBoolean(ARG_IS_EDIT) ?: false
        transactionId = arguments?.getString(ARG_TX_ID)
        prefilledSymbol = arguments?.getString(ARG_SYMBOL)
        selectedType = arguments?.getString(ARG_TYPE) ?: "BUY"
        submitButtonLabel = if (isEditMode) "Save changes" else "Save"
        binding.btnSubmit.text = submitButtonLabel

        setupUI()
        setupListeners()
        setupCostCalculation()
    }

    private fun setupUI() {
        if (isEditMode) {
            binding.tvDialogTitle.text = "Edit Transaction"
            binding.tvDialogSubtitle.text = "Update quantity, price, fee, or execution date."
            binding.layoutTypeToggle.visibility = View.GONE
            binding.tilStockSearch.visibility = View.GONE
            binding.layoutQuickChips.visibility = View.GONE
            binding.rvStockSuggestions.visibility = View.GONE

            binding.cardSelectedStock.visibility = View.VISIBLE
            binding.btnChangeStock.visibility = View.GONE
            binding.tvSelectedSymbol.text = prefilledSymbol ?: ""
            binding.tvSelectedName.text = "Position Asset"
            binding.tvSelectedSector.text = "PSX Equities"
            binding.tvSelectedLetter.text = (prefilledSymbol ?: "S").take(1).uppercase()
            binding.tvSelectedLtp.text = "Recorded Ticker"

            binding.etQuantity.setText(arguments?.getDouble(ARG_QTY)?.toString() ?: "")
            binding.etPrice.setText(arguments?.getDouble(ARG_PRICE)?.toString() ?: "")
            binding.etFee.setText(arguments?.getDouble(ARG_FEE)?.toString() ?: "0.0")
            binding.etDate.setText(arguments?.getString(ARG_DATE) ?: "")
        } else {
            binding.tvDialogTitle.text = "Record Transaction"
            binding.tvDialogSubtitle.text = "Select a verified PSX stock and add order details."
            binding.layoutTypeToggle.visibility = View.VISIBLE

            suggestionAdapter = StockSearchAdapter { stock ->
                selectStock(stock)
            }
            binding.rvStockSuggestions.layoutManager = LinearLayoutManager(requireContext())
            binding.rvStockSuggestions.adapter = suggestionAdapter

            val today = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
            binding.etDate.setText(today)
            updateTypeToggleUI()

            if (!prefilledSymbol.isNullOrBlank()) {
                selectQuickSymbol(prefilledSymbol!!)
            }
        }
    }

    private fun updateTypeToggleUI() {
        if (selectedType == "BUY") {
            binding.btnSelectBuy.setBackgroundColor(Color.parseColor("#18B981"))
            binding.btnSelectBuy.setTextColor(Color.WHITE)
            binding.btnSelectSell.setBackgroundColor(Color.TRANSPARENT)
            binding.btnSelectSell.setTextColor(Color.parseColor("#667085"))
        } else {
            binding.btnSelectSell.setBackgroundColor(Color.parseColor("#EF4444"))
            binding.btnSelectSell.setTextColor(Color.WHITE)
            binding.btnSelectBuy.setBackgroundColor(Color.TRANSPARENT)
            binding.btnSelectBuy.setTextColor(Color.parseColor("#667085"))
        }
    }

    private fun setupListeners() {
        binding.btnSelectBuy.setOnClickListener {
            selectedType = "BUY"
            updateTypeToggleUI()
        }

        binding.btnSelectSell.setOnClickListener {
            selectedType = "SELL"
            updateTypeToggleUI()
        }

        binding.btnCancel.setOnClickListener {
            dismiss()
        }

        binding.btnSubmit.setOnClickListener {
            submitForm()
        }

        binding.btnChangeStock.setOnClickListener {
            clearSelectedStock()
        }

        // Live Search Typeahead (debounced 250ms)
        binding.etStockSearch.doAfterTextChanged { text ->
            val query = text?.toString()?.trim() ?: ""
            searchJob?.cancel()
            if (query.isEmpty()) {
                binding.rvStockSuggestions.visibility = View.GONE
                binding.layoutQuickChips.visibility = View.VISIBLE
            } else {
                searchJob = lifecycleScope.launch {
                    delay(250)
                    performStockSearch(query)
                }
            }
        }

        // Quick Pick Chips
        binding.chipLuck.setOnClickListener { selectQuickSymbol("LUCK") }
        binding.chipOgdc.setOnClickListener { selectQuickSymbol("OGDC") }
        binding.chipSys.setOnClickListener { selectQuickSymbol("SYS") }
        binding.chipHubc.setOnClickListener { selectQuickSymbol("HUBC") }
        binding.chipEngro.setOnClickListener { selectQuickSymbol("ENGRO") }
        binding.chipMebl.setOnClickListener { selectQuickSymbol("MEBL") }

        // Quick Quantity Chips
        binding.chipQty10.setOnClickListener { incrementQuantity(10.0) }
        binding.chipQty50.setOnClickListener { incrementQuantity(50.0) }
        binding.chipQty100.setOnClickListener { incrementQuantity(100.0) }
        binding.chipQty500.setOnClickListener { incrementQuantity(500.0) }
    }

    private fun incrementQuantity(addQty: Double) {
        val current = binding.etQuantity.text?.toString()?.toDoubleOrNull() ?: 0.0
        val updated = current + addQty
        binding.etQuantity.setText(String.format(Locale.US, "%.0f", updated))
        calculateTotalCost()
    }

    private fun setupCostCalculation() {
        val watcher = {
            calculateTotalCost()
        }
        binding.etQuantity.doAfterTextChanged { watcher() }
        binding.etPrice.doAfterTextChanged { watcher() }
        binding.etFee.doAfterTextChanged { watcher() }
    }

    private fun calculateTotalCost() {
        val qty = binding.etQuantity.text?.toString()?.toDoubleOrNull() ?: 0.0
        val price = binding.etPrice.text?.toString()?.toDoubleOrNull() ?: 0.0
        val fee = binding.etFee.text?.toString()?.toDoubleOrNull() ?: 0.0
        val total = (qty * price) + fee
        binding.tvEstimatedTotal.text = "PKR ${currencyFormat.format(total)}"
    }

    private suspend fun performStockSearch(query: String) {
        val result = stockRepository.searchStocks(query, limit = 6)
        if (result.isSuccess) {
            val list = result.getOrDefault(emptyList())
            if (list.isNotEmpty()) {
                binding.layoutQuickChips.visibility = View.GONE
                binding.rvStockSuggestions.visibility = View.VISIBLE
                suggestionAdapter.submitList(list)
            } else {
                binding.rvStockSuggestions.visibility = View.GONE
                binding.layoutQuickChips.visibility = View.VISIBLE
            }
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
        binding.tvFormError.visibility = View.GONE

        // Hide search & suggestions
        binding.tilStockSearch.visibility = View.GONE
        binding.layoutQuickChips.visibility = View.GONE
        binding.rvStockSuggestions.visibility = View.GONE

        // Show locked verified stock card
        binding.cardSelectedStock.visibility = View.VISIBLE
        binding.btnChangeStock.visibility = View.VISIBLE
        binding.tvSelectedSymbol.text = stock.symbol
        binding.tvSelectedName.text = stock.name
        binding.tvSelectedSector.text = stock.sector
        binding.tvSelectedLetter.text = stock.symbol.take(1).uppercase()

        if (knownPrice != null && knownPrice > 0.0) {
            binding.tvSelectedLtp.text = "Market Price: PKR ${currencyFormat.format(knownPrice)}"
            if (binding.etPrice.text.isNullOrBlank()) {
                binding.etPrice.setText(String.format(Locale.US, "%.2f", knownPrice))
            }
            calculateTotalCost()
        } else {
            binding.tvSelectedLtp.text = "Fetching live market price..."
            lifecycleScope.launch {
                val overview = stockRepository.getStockOverview(stock.symbol)
                if (overview.isSuccess) {
                    val price = overview.getOrThrow().price
                    binding.tvSelectedLtp.text = "Market Price: PKR ${currencyFormat.format(price)}"
                    if (binding.etPrice.text.isNullOrBlank()) {
                        binding.etPrice.setText(String.format(Locale.US, "%.2f", price))
                    }
                    calculateTotalCost()
                } else {
                    binding.tvSelectedLtp.text = "Live price unavailable on PSX feed"
                }
            }
        }
    }

    private fun clearSelectedStock() {
        verifiedSelectedStock = null
        binding.cardSelectedStock.visibility = View.GONE
        binding.tilStockSearch.visibility = View.VISIBLE
        binding.layoutQuickChips.visibility = View.VISIBLE
        binding.rvStockSuggestions.visibility = View.GONE
        binding.etStockSearch.text?.clear()
    }

    private fun submitForm() {
        if (isSubmitting) return
        binding.tvFormError.visibility = View.GONE

        val symbol = if (isEditMode) {
            prefilledSymbol.orEmpty()
        } else {
            verifiedSelectedStock?.symbol.orEmpty()
        }

        // Strict verification: User cannot submit without picking a real PSX stock!
        if (symbol.isBlank()) {
            showError("Please search and select a verified PSX stock from the list.")
            return
        }

        val qty = binding.etQuantity.text?.toString()?.toDoubleOrNull()
        val price = binding.etPrice.text?.toString()?.toDoubleOrNull()
        val fee = binding.etFee.text?.toString()?.toDoubleOrNull() ?: 0.0
        val date = binding.etDate.text?.toString()?.trim().orEmpty()

        if (qty == null || qty <= 0) {
            showError("Please enter a valid positive quantity.")
            return
        }
        if (price == null || price <= 0) {
            showError("Please enter a valid positive execution price.")
            return
        }
        if (date.isBlank() || !date.matches(Regex("^\\d{4}-\\d{2}-\\d{2}$"))) {
            showError("Please enter date in format YYYY-MM-DD.")
            return
        }

        isSubmitting = true
        binding.btnSubmit.isEnabled = false
        binding.btnSubmit.text = if (isEditMode) "Updating…" else "Saving…"
        binding.btnCancel.isEnabled = false
        binding.layoutSavingTransaction.visibility = View.VISIBLE
        binding.tvSavingTransaction.text = if (isEditMode) "Updating transaction…" else "Saving $selectedType transaction…"

        lifecycleScope.launch {
            if (isEditMode) {
                val txId = transactionId.orEmpty()
                val result = updateUseCase(
                    transactionId = txId,
                    quantity = qty,
                    price = price,
                    fee = fee,
                    date = date
                )
                if (result.isSuccess) {
                    Toast.makeText(requireContext(), "Transaction updated", Toast.LENGTH_SHORT).show()
                    onTransactionSaved?.invoke()
                    dismiss()
                } else {
                    resetSubmittingState()
                    showError(result.exceptionOrNull()?.message ?: "Failed to update transaction.")
                }
            } else {
                val result = createUseCase(
                    symbol = symbol,
                    type = selectedType,
                    quantity = qty,
                    price = price,
                    fee = fee,
                    date = date
                )
                if (result.isSuccess) {
                    Toast.makeText(requireContext(), "$selectedType transaction saved", Toast.LENGTH_SHORT).show()
                    onTransactionSaved?.invoke()
                    dismiss()
                } else {
                    resetSubmittingState()
                    showError(result.exceptionOrNull()?.message ?: "Failed to create transaction.")
                }
            }
        }
    }

    private fun resetSubmittingState() {
        isSubmitting = false
        binding.layoutSavingTransaction.visibility = View.GONE
        binding.btnSubmit.isEnabled = true
        binding.btnSubmit.text = submitButtonLabel
        binding.btnCancel.isEnabled = true
    }

    private fun showError(msg: String) {
        binding.tvFormError.text = msg
        binding.tvFormError.visibility = View.VISIBLE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        searchJob?.cancel()
        _binding = null
    }
}
