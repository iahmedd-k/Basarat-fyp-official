package com.fyp.basarattradeinvest.feature.shariah.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemShariahStockBinding
import com.fyp.basarattradeinvest.domain.model.shariah.ShariahStock
import java.util.Locale

class ShariahStockAdapter(
    private val onItemClick: (ShariahStock) -> Unit = {}
) : ListAdapter<ShariahStock, ShariahStockAdapter.StockViewHolder>(StockDiffCallback()) {

    companion object {
        private const val UNAVAILABLE = "—"
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): StockViewHolder {
        val binding = ItemShariahStockBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return StockViewHolder(binding)
    }

    override fun onBindViewHolder(holder: StockViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class StockViewHolder(
        private val binding: ItemShariahStockBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: ShariahStock) {
            val context = binding.root.context

            binding.tvStockSymbol.text = item.symbol
            binding.tvStockCode.text = item.companyName

            binding.tvStockPrice.text = item.price?.let { String.format(Locale.US, "%.2f", it) }
                ?: UNAVAILABLE

            val changePercent = item.changePercent
            if (changePercent != null) {
                val prefix = if (changePercent >= 0) "+" else ""
                binding.tvStockChange.text = String.format(Locale.US, "%s%.2f%%", prefix, changePercent)
                val changeColor = if (changePercent >= 0) R.color.color_positive else R.color.color_negative
                binding.tvStockChange.setTextColor(ContextCompat.getColor(context, changeColor))
            } else {
                binding.tvStockChange.text = UNAVAILABLE
                binding.tvStockChange.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
            }

            val rate = item.purificationRate
            binding.tvStockPurification.text = if (rate != null) {
                String.format(Locale.US, "%.2f%%", rate * 100)
            } else {
                UNAVAILABLE
            }

            binding.root.setOnClickListener {
                onItemClick(item)
            }
        }
    }

    class StockDiffCallback : DiffUtil.ItemCallback<ShariahStock>() {
        override fun areItemsTheSame(oldItem: ShariahStock, newItem: ShariahStock): Boolean {
            return oldItem.symbol == newItem.symbol
        }

        override fun areContentsTheSame(oldItem: ShariahStock, newItem: ShariahStock): Boolean {
            return oldItem == newItem
        }
    }
}
