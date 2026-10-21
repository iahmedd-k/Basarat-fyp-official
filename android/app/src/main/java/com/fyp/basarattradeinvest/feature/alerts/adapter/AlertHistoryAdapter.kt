package com.fyp.basarattradeinvest.feature.alerts.adapter

import android.graphics.Typeface
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemAlertHistoryBinding
import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem

class AlertHistoryAdapter(
    private val onAlertClick: (AlertItem) -> Unit
) : ListAdapter<AlertItem, AlertHistoryAdapter.AlertHistoryViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AlertHistoryViewHolder {
        val binding = ItemAlertHistoryBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return AlertHistoryViewHolder(binding)
    }

    override fun onBindViewHolder(holder: AlertHistoryViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class AlertHistoryViewHolder(
        private val binding: ItemAlertHistoryBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: AlertItem) {
            val context = binding.root.context

            binding.tvAlertTitle.text = item.title
            binding.tvAlertMessage.text = item.message ?: "Alert condition was triggered."
            binding.tvAlertTime.text = item.formattedTime

            // Unread state visual distinction
            if (!item.isRead) {
                binding.viewUnreadDot.visibility = View.VISIBLE
                binding.tvAlertTitle.setTypeface(null, Typeface.BOLD)
                binding.tvAlertTitle.setTextColor(ContextCompat.getColor(context, R.color.color_text_primary))
                binding.cardAlertItem.strokeColor = ContextCompat.getColor(context, R.color.color_brand_primary)
            } else {
                binding.viewUnreadDot.visibility = View.GONE
                binding.tvAlertTitle.setTypeface(null, Typeface.NORMAL)
                binding.tvAlertTitle.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
                binding.cardAlertItem.strokeColor = ContextCompat.getColor(context, R.color.color_border)
            }

            binding.root.setOnClickListener {
                onAlertClick(item)
            }
        }
    }

    companion object {
        private val DiffCallback = object : DiffUtil.ItemCallback<AlertItem>() {
            override fun areItemsTheSame(oldItem: AlertItem, newItem: AlertItem): Boolean {
                return oldItem.id == newItem.id
            }

            override fun areContentsTheSame(oldItem: AlertItem, newItem: AlertItem): Boolean {
                return oldItem == newItem
            }
        }
    }
}
