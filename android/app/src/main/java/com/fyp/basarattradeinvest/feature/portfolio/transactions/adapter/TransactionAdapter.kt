package com.fyp.basarattradeinvest.feature.portfolio.transactions.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemPortfolioTransactionBinding
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import java.text.NumberFormat
import java.util.Locale

class TransactionAdapter(
    private val onItemClick: (String) -> Unit
) : ListAdapter<PortfolioTransaction, TransactionAdapter.TransactionViewHolder>(TransactionDiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TransactionViewHolder {
        val binding = ItemPortfolioTransactionBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return TransactionViewHolder(binding, onItemClick)
    }

    override fun onBindViewHolder(holder: TransactionViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class TransactionViewHolder(
        private val binding: ItemPortfolioTransactionBinding,
        private val onItemClick: (String) -> Unit
    ) : RecyclerView.ViewHolder(binding.root) {

        private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 2
            maximumFractionDigits = 2
        }

        fun bind(item: PortfolioTransaction) {
            val isBuy = item.transactionType.equals("BUY", ignoreCase = true)
            binding.tvBadgeType.text = if (isBuy) "BUY" else "SELL"
            if (isBuy) {
                binding.tvBadgeType.setBackgroundResource(R.drawable.bg_badge_buy)
                binding.tvBadgeType.setTextColor(
                    ContextCompat.getColor(binding.root.context, R.color.color_positive)
                )
            } else {
                binding.tvBadgeType.setBackgroundResource(R.drawable.bg_badge_sell)
                binding.tvBadgeType.setTextColor(
                    ContextCompat.getColor(binding.root.context, R.color.color_negative)
                )
            }

            binding.tvTxSymbol.text = item.symbol

            val total = item.quantity * item.price
            binding.tvTxTotal.text = "PKR ${currencyFormat.format(total)}"

            binding.tvTxDetails.text = String.format(
                Locale.US,
                "%.0f shares @ PKR %s",
                item.quantity,
                currencyFormat.format(item.price)
            )

            binding.tvTxFee.text = "Fee: PKR ${currencyFormat.format(item.fee)}"
            binding.tvTxDate.text = item.transactionDate

            binding.root.setOnClickListener {
                onItemClick(item.id)
            }
        }
    }

    object TransactionDiffCallback : DiffUtil.ItemCallback<PortfolioTransaction>() {
        override fun areItemsTheSame(oldItem: PortfolioTransaction, newItem: PortfolioTransaction): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: PortfolioTransaction, newItem: PortfolioTransaction): Boolean {
            return oldItem == newItem
        }
    }
}
