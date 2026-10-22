package com.fyp.basarattradeinvest.feature.dashboard.adapter

import android.graphics.Color
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemHomeHoldingBinding
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import java.text.NumberFormat
import java.util.Locale

class HomeHoldingAdapter(
    private val onItemClick: (String) -> Unit
) : ListAdapter<HoldingItem, HomeHoldingAdapter.ViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemHomeHoldingBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return ViewHolder(binding, onItemClick)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class ViewHolder(
        private val binding: ItemHomeHoldingBinding,
        private val onItemClick: (String) -> Unit
    ) : RecyclerView.ViewHolder(binding.root) {

        private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 0
            maximumFractionDigits = 0
        }

        private val priceFormat = NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 2
            maximumFractionDigits = 2
        }

        fun bind(item: HoldingItem) {
            // Initials avatar
            val initials = if (item.symbol.length <= 2) item.symbol else item.symbol.take(2)
            binding.tvHoldingAvatar.text = initials.uppercase(Locale.ROOT)

            binding.tvHoldingSymbol.text = item.symbol

            val sharesCount = String.format(Locale.US, "%,.0f", item.quantity)
            val companyShort = if (item.companyName.isNotBlank() && item.companyName != item.symbol) {
                item.companyName.take(18)
            } else {
                item.sector
            }
            binding.tvHoldingSubtitle.text = "$companyShort • $sharesCount sh..."

            // Market value
            val curPrice = item.currentPrice ?: item.averageCost
            val marketVal = item.marketValue ?: (item.quantity * curPrice)
            binding.tvHoldingValue.text = "Rs. ${currencyFormat.format(marketVal)}"

            // Price and change %
            val pnlPct = item.unrealizedPnlPercent ?: 0.0
            val sign = if (pnlPct >= 0) "+" else ""
            val priceStr = "Rs. ${priceFormat.format(curPrice)}"
            val changeStr = "$sign${String.format(Locale.US, "%.2f%%", pnlPct)}"
            binding.tvHoldingPriceChange.text = "$priceStr $changeStr"

            if (pnlPct >= 0) {
                binding.tvHoldingPriceChange.setTextColor(Color.parseColor("#18B981"))
            } else {
                binding.tvHoldingPriceChange.setTextColor(Color.parseColor("#EF4444"))
            }

            binding.root.setOnClickListener {
                onItemClick(item.symbol)
            }
        }
    }

    object DiffCallback : DiffUtil.ItemCallback<HoldingItem>() {
        override fun areItemsTheSame(oldItem: HoldingItem, newItem: HoldingItem): Boolean {
            return oldItem.symbol == newItem.symbol
        }

        override fun areContentsTheSame(oldItem: HoldingItem, newItem: HoldingItem): Boolean {
            return oldItem == newItem
        }
    }
}
