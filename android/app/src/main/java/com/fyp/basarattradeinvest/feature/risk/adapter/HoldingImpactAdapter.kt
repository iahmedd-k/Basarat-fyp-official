package com.fyp.basarattradeinvest.feature.risk.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemHoldingImpactBinding
import com.fyp.basarattradeinvest.domain.model.risk.HoldingImpact
import java.text.NumberFormat
import java.util.Locale

class HoldingImpactAdapter : ListAdapter<HoldingImpact, HoldingImpactAdapter.HoldingImpactViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): HoldingImpactViewHolder {
        val binding = ItemHoldingImpactBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return HoldingImpactViewHolder(binding)
    }

    override fun onBindViewHolder(holder: HoldingImpactViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class HoldingImpactViewHolder(private val binding: ItemHoldingImpactBinding) : RecyclerView.ViewHolder(binding.root) {
        private val currencyFormat = NumberFormat.getNumberInstance(Locale.US).apply {
            minimumFractionDigits = 2
            maximumFractionDigits = 2
        }

        fun bind(item: HoldingImpact) {
            binding.tvHoldingSymbol.text = item.symbol
            if (!item.name.isNullOrBlank()) {
                binding.tvHoldingName.visibility = View.VISIBLE
                binding.tvHoldingName.text = item.name
            } else {
                binding.tvHoldingName.visibility = View.GONE
            }

            val pct = item.impactPct
            if (pct != null) {
                val pctVal = pct * 100
                val prefix = if (pctVal > 0) "+" else ""
                binding.tvHoldingImpactPct.text = String.format(Locale.US, "%s%.1f%%", prefix, pctVal)
                binding.tvHoldingImpactPct.visibility = View.VISIBLE
            } else {
                binding.tvHoldingImpactPct.visibility = View.GONE
            }

            val impactVal = item.impactValue
            if (impactVal != null) {
                val prefix = if (impactVal > 0) "+PKR " else "-PKR "
                binding.tvHoldingImpactVal.text = String.format(Locale.US, "%s%s", prefix, currencyFormat.format(Math.abs(impactVal)))
                binding.tvHoldingImpactVal.visibility = View.VISIBLE
            } else {
                binding.tvHoldingImpactVal.visibility = View.GONE
            }
        }
    }

    companion object {
        private val DiffCallback = object : DiffUtil.ItemCallback<HoldingImpact>() {
            override fun areItemsTheSame(oldItem: HoldingImpact, newItem: HoldingImpact): Boolean {
                return oldItem.symbol == newItem.symbol
            }

            override fun areContentsTheSame(oldItem: HoldingImpact, newItem: HoldingImpact): Boolean {
                return oldItem == newItem
            }
        }
    }
}
