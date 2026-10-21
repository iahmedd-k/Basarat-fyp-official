package com.fyp.basarattradeinvest.feature.risk.adapter

import android.graphics.Color
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemMcPercentileBinding
import com.fyp.basarattradeinvest.domain.model.risk.PercentileEntry
import java.util.Locale

class MonteCarloPercentilesAdapter : ListAdapter<PercentileEntry, MonteCarloPercentilesAdapter.PercentileViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): PercentileViewHolder {
        val binding = ItemMcPercentileBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return PercentileViewHolder(binding)
    }

    override fun onBindViewHolder(holder: PercentileViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class PercentileViewHolder(private val binding: ItemMcPercentileBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(item: PercentileEntry) {
            binding.tvPercentileLabel.text = item.percentile
            val pctVal = item.value * 100
            val prefix = if (pctVal > 0) "+" else ""
            binding.tvPercentileValue.text = String.format(Locale.US, "%s%.2f%%", prefix, pctVal)

            if (pctVal < 0) {
                binding.tvPercentileValue.setTextColor(Color.parseColor("#EF4444")) // Negative red
            } else if (pctVal > 0) {
                binding.tvPercentileValue.setTextColor(Color.parseColor("#18B981")) // Positive green
            } else {
                binding.tvPercentileValue.setTextColor(Color.parseColor("#111827"))
            }
        }
    }

    companion object {
        private val DiffCallback = object : DiffUtil.ItemCallback<PercentileEntry>() {
            override fun areItemsTheSame(oldItem: PercentileEntry, newItem: PercentileEntry): Boolean {
                return oldItem.percentile == newItem.percentile
            }

            override fun areContentsTheSame(oldItem: PercentileEntry, newItem: PercentileEntry): Boolean {
                return oldItem == newItem
            }
        }
    }
}
