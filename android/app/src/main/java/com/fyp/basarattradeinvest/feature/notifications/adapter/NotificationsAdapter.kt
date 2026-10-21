package com.fyp.basarattradeinvest.feature.notifications.adapter

import android.graphics.Typeface
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemNotificationBinding
import com.fyp.basarattradeinvest.domain.model.alerts.InAppNotification

class NotificationsAdapter(
    private val onItemClick: (InAppNotification) -> Unit
) : ListAdapter<InAppNotification, NotificationsAdapter.NotificationViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): NotificationViewHolder {
        val binding = ItemNotificationBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return NotificationViewHolder(binding)
    }

    override fun onBindViewHolder(holder: NotificationViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class NotificationViewHolder(
        private val binding: ItemNotificationBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: InAppNotification) {
            val context = binding.root.context

            binding.tvNotificationTitle.text = item.title
            binding.tvNotificationMessage.text = item.message ?: ""
            binding.tvNotificationTime.text = item.formattedTime

            if (!item.isRead) {
                binding.viewUnreadDot.visibility = View.VISIBLE
                binding.tvNotificationTitle.setTypeface(null, Typeface.BOLD)
                binding.tvNotificationTitle.setTextColor(ContextCompat.getColor(context, R.color.color_text_primary))
                binding.cardNotification.strokeColor = ContextCompat.getColor(context, R.color.color_brand_primary)
            } else {
                binding.viewUnreadDot.visibility = View.GONE
                binding.tvNotificationTitle.setTypeface(null, Typeface.NORMAL)
                binding.tvNotificationTitle.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
                binding.cardNotification.strokeColor = ContextCompat.getColor(context, R.color.color_border)
            }

            binding.root.setOnClickListener {
                onItemClick(item)
            }
        }
    }

    companion object {
        private val DiffCallback = object : DiffUtil.ItemCallback<InAppNotification>() {
            override fun areItemsTheSame(oldItem: InAppNotification, newItem: InAppNotification): Boolean {
                return oldItem.id == newItem.id
            }

            override fun areContentsTheSame(oldItem: InAppNotification, newItem: InAppNotification): Boolean {
                return oldItem == newItem
            }
        }
    }
}
