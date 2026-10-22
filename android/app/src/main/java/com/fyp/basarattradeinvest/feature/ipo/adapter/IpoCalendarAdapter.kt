package com.fyp.basarattradeinvest.feature.ipo.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemIpoCalendarEventBinding
import com.fyp.basarattradeinvest.domain.model.ipo.IpoCalendarEvent
import com.fyp.basarattradeinvest.feature.common.FormatUtils

class IpoCalendarAdapter :
    ListAdapter<IpoCalendarEvent, IpoCalendarAdapter.EventViewHolder>(DiffCallback) {

    inner class EventViewHolder(
        private val binding: ItemIpoCalendarEventBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(event: IpoCalendarEvent) {
            binding.tvEventDate.text = FormatUtils.dateFull(event.eventDate)
            binding.tvEventType.text = FormatUtils.ipoEventType(event.eventType)
            binding.tvEventCompany.text = event.companyName
            binding.tvEventSymbol.text = event.symbol

            if (event.priceInfo.isNullOrBlank()) {
                binding.tvEventPriceInfo.visibility = View.GONE
            } else {
                binding.tvEventPriceInfo.visibility = View.VISIBLE
                binding.tvEventPriceInfo.text = event.priceInfo
            }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): EventViewHolder {
        val binding = ItemIpoCalendarEventBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return EventViewHolder(binding)
    }

    override fun onBindViewHolder(holder: EventViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    companion object DiffCallback : DiffUtil.ItemCallback<IpoCalendarEvent>() {
        override fun areItemsTheSame(oldItem: IpoCalendarEvent, newItem: IpoCalendarEvent): Boolean =
            oldItem.symbol == newItem.symbol &&
                oldItem.eventType == newItem.eventType &&
                oldItem.eventDate == newItem.eventDate

        override fun areContentsTheSame(oldItem: IpoCalendarEvent, newItem: IpoCalendarEvent): Boolean =
            oldItem == newItem
    }
}
