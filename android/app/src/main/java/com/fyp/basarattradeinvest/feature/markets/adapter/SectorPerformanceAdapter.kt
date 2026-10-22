package com.fyp.basarattradeinvest.feature.markets.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemSectorPerformanceBinding
import com.fyp.basarattradeinvest.domain.model.market.SectorPerformance
import java.util.Locale

class SectorPerformanceAdapter(
    private val onItemClick: (SectorPerformance) -> Unit = {}
) : ListAdapter<SectorPerformance, SectorPerformanceAdapter.SectorViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): SectorViewHolder {
        val binding = ItemSectorPerformanceBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return SectorViewHolder(binding)
    }

    override fun onBindViewHolder(holder: SectorViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class SectorViewHolder(
        private val binding: ItemSectorPerformanceBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(sector: SectorPerformance) {
            binding.tvSectorName.text = sector.sectorName
            val prefix = if (sector.changePercent >= 0) "+" else ""
            binding.tvSectorChange.text = String.format(Locale.US, "%s%.2f%%", prefix, sector.changePercent)

            val colorRes = if (sector.isPositive) R.color.color_positive else R.color.color_negative
            binding.tvSectorChange.setTextColor(
                ContextCompat.getColor(binding.root.context, colorRes)
            )

            binding.tvSectorVolume.text = "Vol: ${sector.volume}"

            binding.root.setOnClickListener {
                onItemClick(sector)
            }
        }
    }

    companion object DiffCallback : DiffUtil.ItemCallback<SectorPerformance>() {
        override fun areItemsTheSame(oldItem: SectorPerformance, newItem: SectorPerformance): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: SectorPerformance, newItem: SectorPerformance): Boolean {
            return oldItem == newItem
        }
    }
}
