package com.fyp.basarattradeinvest.feature.news.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemCorporateEventBinding
import com.fyp.basarattradeinvest.domain.model.market.CorporateEvent

class CorporateEventAdapter(
    private val onEventClick: (CorporateEvent) -> Unit = {}
) : ListAdapter<CorporateEvent, CorporateEventAdapter.EventViewHolder>(EventDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): EventViewHolder {
        val binding = ItemCorporateEventBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return EventViewHolder(binding)
    }

    override fun onBindViewHolder(holder: EventViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class EventViewHolder(
        private val binding: ItemCorporateEventBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: CorporateEvent) {
            binding.tvEventType.text = item.eventType
            binding.tvEventSymbol.text = item.symbol
            binding.tvEventCompany.text = item.companyName
            binding.tvEventDate.text = item.eventDate
            binding.tvEventDescription.text = item.description
            binding.tvEventClosureLabel.text = item.bookClosure
            binding.tvEventSource.text = item.sourceNotice

            binding.root.setOnClickListener {
                onEventClick(item)
            }
        }
    }

    class EventDiffCallback : DiffUtil.ItemCallback<CorporateEvent>() {
        override fun areItemsTheSame(oldItem: CorporateEvent, newItem: CorporateEvent): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: CorporateEvent, newItem: CorporateEvent): Boolean {
            return oldItem == newItem
        }
    }
}
