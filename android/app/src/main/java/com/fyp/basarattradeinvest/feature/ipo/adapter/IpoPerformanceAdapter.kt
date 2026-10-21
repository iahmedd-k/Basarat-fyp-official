package com.fyp.basarattradeinvest.feature.ipo.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemIpoPerformanceBinding
import com.fyp.basarattradeinvest.domain.model.ipo.IpoPerformanceItem
import com.fyp.basarattradeinvest.feature.common.FormatUtils

class IpoPerformanceAdapter :
    ListAdapter<IpoPerformanceItem, IpoPerformanceAdapter.PerfViewHolder>(DiffCallback) {

    inner class PerfViewHolder(
        private val binding: ItemIpoPerformanceBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: IpoPerformanceItem) {
            val context = binding.root.context

            binding.tvPerfSymbol.text = item.symbol
            binding.tvPerfCompany.text = item.companyName

            val parts = mutableListOf<String>()
            if (!item.sector.isNullOrBlank()) parts.add(item.sector)
            FormatUtils.parseDate(item.listingDate)?.let {
                parts.add("Listed ${FormatUtils.dateFull(it)}")
            }
            if (parts.isEmpty()) {
                binding.tvPerfSector.visibility = View.GONE
            } else {
                binding.tvPerfSector.visibility = View.VISIBLE
                binding.tvPerfSector.text = parts.joinToString(" · ")
            }

            binding.tvPerfOfferPrice.text = FormatUtils.price(item.offerPrice)

            bindReturn(binding.tvPerfFirstDay, item.firstDayReturnPct)
            bindReturn(binding.tvPerfTotalReturn, item.totalReturnPct)

            // Keep the label color neutral so the sign conveys direction
            val firstColor = returnColor(item.firstDayReturnPct)
            binding.tvPerfFirstDay.setTextColor(ContextCompat.getColor(context, firstColor))
            val totalColor = returnColor(item.totalReturnPct)
            binding.tvPerfTotalReturn.setTextColor(ContextCompat.getColor(context, totalColor))
        }

        private fun bindReturn(view: android.widget.TextView, value: Double?) {
            view.text = FormatUtils.percentSigned(value)
        }

        private fun returnColor(value: Double?): Int = when {
            value == null -> R.color.color_text_primary
            value >= 0 -> R.color.color_positive
            else -> R.color.color_negative
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): PerfViewHolder {
        val binding = ItemIpoPerformanceBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return PerfViewHolder(binding)
    }

    override fun onBindViewHolder(holder: PerfViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    companion object DiffCallback : DiffUtil.ItemCallback<IpoPerformanceItem>() {
        override fun areItemsTheSame(oldItem: IpoPerformanceItem, newItem: IpoPerformanceItem): Boolean =
            oldItem.symbol == newItem.symbol

        override fun areContentsTheSame(oldItem: IpoPerformanceItem, newItem: IpoPerformanceItem): Boolean =
            oldItem == newItem
    }
}
