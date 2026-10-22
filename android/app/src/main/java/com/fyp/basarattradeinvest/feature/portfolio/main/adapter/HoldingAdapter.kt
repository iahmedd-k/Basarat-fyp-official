package com.fyp.basarattradeinvest.feature.portfolio.main.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemPortfolioHoldingBinding
import com.fyp.basarattradeinvest.domain.model.portfolio.HoldingItem
import java.text.NumberFormat
import java.util.Locale

class HoldingAdapter(
    private val onItemClick: (String) -> Unit
) : ListAdapter<HoldingItem, HoldingAdapter.HoldingViewHolder>(HoldingDiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): HoldingViewHolder {
        val binding = ItemPortfolioHoldingBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return HoldingViewHolder(binding, onItemClick)
    }

    override fun onBindViewHolder(holder: HoldingViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class HoldingViewHolder(
        private val binding: ItemPortfolioHoldingBinding,
        private val onItemClick: (String) -> Unit
    ) : RecyclerView.ViewHolder(binding.root) {

        private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 2
            maximumFractionDigits = 2
        }

        fun bind(item: HoldingItem) {
            binding.tvHoldingSymbol.text = item.symbol
            val weight = item.portfolioWeight ?: 0.0
            binding.tvHoldingWeight.text = String.format(Locale.US, "%.1f%%", weight)

            val company = if (item.companyName.isNotBlank() && item.companyName != item.symbol) {
                "${item.companyName} • ${item.sector}"
            } else {
                item.sector
            }
            binding.tvHoldingCompany.text = company

            val curPrice = item.currentPrice ?: item.averageCost
            binding.tvHoldingCurrentPrice.text = "PKR ${currencyFormat.format(curPrice)}"

            val marketVal = item.marketValue ?: (item.quantity * curPrice)
            binding.tvHoldingMarketValue.text = "Val: PKR ${currencyFormat.format(marketVal)}"

            binding.tvHoldingSharesCost.text = String.format(
                Locale.US,
                "%.0f shares • Avg: PKR %s",
                item.quantity,
                currencyFormat.format(item.averageCost)
            )

            val pnl = item.unrealizedPnl ?: 0.0
            val pnlPct = item.unrealizedPnlPercent ?: 0.0
            val prefix = if (pnl >= 0) "+" else ""
            val sign = if (pnl >= 0) "+" else ""
            binding.tvHoldingPnl.text = String.format(
                Locale.US,
                "%sPKR %s (%s%.2f%%)",
                prefix,
                currencyFormat.format(pnl),
                sign,
                pnlPct
            )

            if (pnl >= 0) {
                binding.tvHoldingPnl.setTextColor(
                    ContextCompat.getColor(binding.root.context, R.color.color_positive)
                )
            } else {
                binding.tvHoldingPnl.setTextColor(
                    ContextCompat.getColor(binding.root.context, R.color.color_negative)
                )
            }

            binding.root.setOnClickListener {
                onItemClick(item.symbol)
            }
        }
    }

    object HoldingDiffCallback : DiffUtil.ItemCallback<HoldingItem>() {
        override fun areItemsTheSame(oldItem: HoldingItem, newItem: HoldingItem): Boolean {
            return oldItem.symbol == newItem.symbol
        }

        override fun areContentsTheSame(oldItem: HoldingItem, newItem: HoldingItem): Boolean {
            return oldItem == newItem
        }
    }
}
