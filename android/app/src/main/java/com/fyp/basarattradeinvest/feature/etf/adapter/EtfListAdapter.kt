package com.fyp.basarattradeinvest.feature.etf.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemEtfCardBinding
import com.fyp.basarattradeinvest.domain.model.etf.EtfItem
import com.fyp.basarattradeinvest.feature.common.FormatUtils

class EtfListAdapter(
    private val onItemClick: (EtfItem) -> Unit = {}
) : ListAdapter<EtfItem, EtfListAdapter.EtfViewHolder>(DiffCallback) {

    inner class EtfViewHolder(
        private val binding: ItemEtfCardBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: EtfItem) {
            val context = binding.root.context

            binding.tvEtfSymbol.text = item.symbol
            binding.tvEtfName.text = item.name

            binding.ivEtfShariah.visibility =
                if (item.isShariahCompliant) View.VISIBLE else View.GONE

            binding.tvEtfPrice.text = FormatUtils.price(item.currentPrice)

            if (item.changePercent == null) {
                binding.tvEtfChange.text = FormatUtils.NA
                binding.tvEtfChange.setTextColor(
                    ContextCompat.getColor(context, R.color.color_text_secondary)
                )
            } else {
                binding.tvEtfChange.text = FormatUtils.percentSigned(item.changePercent)
                val colorRes =
                    if (item.changePercent >= 0) R.color.color_positive else R.color.color_negative
                binding.tvEtfChange.setTextColor(ContextCompat.getColor(context, colorRes))
            }

            if (item.fundManager.isNullOrBlank()) {
                binding.tvEtfManager.visibility = View.GONE
            } else {
                binding.tvEtfManager.visibility = View.VISIBLE
                binding.tvEtfManager.text = item.fundManager
            }

            if (item.category.isNullOrBlank()) {
                binding.tvEtfCategory.visibility = View.GONE
            } else {
                binding.tvEtfCategory.visibility = View.VISIBLE
                binding.tvEtfCategory.text = item.category
            }

            binding.root.setOnClickListener { onItemClick(item) }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): EtfViewHolder {
        val binding = ItemEtfCardBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return EtfViewHolder(binding)
    }

    override fun onBindViewHolder(holder: EtfViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    companion object DiffCallback : DiffUtil.ItemCallback<EtfItem>() {
        override fun areItemsTheSame(oldItem: EtfItem, newItem: EtfItem): Boolean =
            oldItem.symbol == newItem.symbol

        override fun areContentsTheSame(oldItem: EtfItem, newItem: EtfItem): Boolean =
            oldItem == newItem
    }
}
