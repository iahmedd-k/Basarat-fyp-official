package com.fyp.basarattradeinvest.feature.etf.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemEtfHistoryRowBinding
import com.fyp.basarattradeinvest.domain.model.etf.EtfHistoryEntry
import com.fyp.basarattradeinvest.feature.common.FormatUtils

class EtfHistoryAdapter :
    ListAdapter<EtfHistoryEntry, EtfHistoryAdapter.HistoryViewHolder>(DiffCallback) {

    inner class HistoryViewHolder(
        private val binding: ItemEtfHistoryRowBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(entry: EtfHistoryEntry) {
            binding.tvHistDate.text = FormatUtils.dateShort(entry.date)
            binding.tvHistOpen.text = FormatUtils.price(entry.open)
            binding.tvHistHigh.text = FormatUtils.price(entry.high)
            binding.tvHistLow.text = FormatUtils.price(entry.low)
            binding.tvHistClose.text = FormatUtils.price(entry.close)
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): HistoryViewHolder {
        val binding = ItemEtfHistoryRowBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return HistoryViewHolder(binding)
    }

    override fun onBindViewHolder(holder: HistoryViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    companion object DiffCallback : DiffUtil.ItemCallback<EtfHistoryEntry>() {
        override fun areItemsTheSame(oldItem: EtfHistoryEntry, newItem: EtfHistoryEntry): Boolean =
            oldItem.date == newItem.date

        override fun areContentsTheSame(oldItem: EtfHistoryEntry, newItem: EtfHistoryEntry): Boolean =
            oldItem == newItem
    }
}
