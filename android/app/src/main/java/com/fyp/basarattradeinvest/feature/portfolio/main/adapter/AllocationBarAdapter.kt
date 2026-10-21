package com.fyp.basarattradeinvest.feature.portfolio.main.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemAllocationItemBinding
import java.text.NumberFormat
import java.util.Locale

data class AllocationDisplayItem(
    val label: String,
    val percentage: Double,
    val marketValue: Double
)

class AllocationBarAdapter : ListAdapter<AllocationDisplayItem, AllocationBarAdapter.AllocationViewHolder>(AllocationDiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AllocationViewHolder {
        val binding = ItemAllocationItemBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return AllocationViewHolder(binding)
    }

    override fun onBindViewHolder(holder: AllocationViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class AllocationViewHolder(
        private val binding: ItemAllocationItemBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 2
            maximumFractionDigits = 2
        }

        fun bind(item: AllocationDisplayItem) {
            binding.tvAllocationLabel.text = item.label
            binding.tvAllocationPercent.text = String.format(Locale.US, "%.1f%%", item.percentage)
            binding.progressAllocation.progress = item.percentage.toInt().coerceIn(0, 100)
            binding.tvAllocationValue.text = "PKR ${currencyFormat.format(item.marketValue)}"
        }
    }

    object AllocationDiffCallback : DiffUtil.ItemCallback<AllocationDisplayItem>() {
        override fun areItemsTheSame(oldItem: AllocationDisplayItem, newItem: AllocationDisplayItem): Boolean {
            return oldItem.label == newItem.label
        }

        override fun areContentsTheSame(oldItem: AllocationDisplayItem, newItem: AllocationDisplayItem): Boolean {
            return oldItem == newItem
        }
    }
}
