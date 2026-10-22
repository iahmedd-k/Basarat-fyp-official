package com.fyp.basarattradeinvest.feature.community.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemCommunityNotificationBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotification

class CommunityNotificationAdapter(
    private val onNotificationClick: (CommunityNotification) -> Unit
) : ListAdapter<CommunityNotification, CommunityNotificationAdapter.NotificationViewHolder>(NotificationDiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): NotificationViewHolder {
        val binding = ItemCommunityNotificationBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return NotificationViewHolder(binding)
    }

    override fun onBindViewHolder(holder: NotificationViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class NotificationViewHolder(private val binding: ItemCommunityNotificationBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(notification: CommunityNotification) {
            val context = binding.root.context

            binding.tvNotifTitle.text = notification.title
            binding.tvNotifMessage.text = notification.message
            binding.tvNotifTime.text = formatTime(notification.createdAt)

            // Read/unread dot & background
            if (notification.isRead) {
                binding.viewUnreadDot.visibility = View.GONE
                binding.cardNotification.setCardBackgroundColor(ContextCompat.getColor(context, R.color.color_surface))
            } else {
                binding.viewUnreadDot.visibility = View.VISIBLE
                binding.cardNotification.setCardBackgroundColor(ContextCompat.getColor(context, R.color.color_surface_elevated))
            }

            // Type icon selection
            val iconRes = when (notification.type) {
                "POST_LIKED" -> R.drawable.ic_thumb_up
                "POST_COMMENTED", "COMMENT_REPLIED" -> R.drawable.ic_comment
                "USER_FOLLOWED" -> R.drawable.ic_person
                else -> R.drawable.ic_alert_bell
            }
            binding.ivNotifTypeIcon.setImageResource(iconRes)

            binding.root.setOnClickListener {
                onNotificationClick(notification)
            }
        }

        private fun formatTime(rawIso: String): String {
            return try {
                if (rawIso.length >= 16) rawIso.substring(11, 16) else rawIso
            } catch (e: Exception) {
                rawIso
            }
        }
    }

    companion object {
        private val NotificationDiffCallback = object : DiffUtil.ItemCallback<CommunityNotification>() {
            override fun areItemsTheSame(oldItem: CommunityNotification, newItem: CommunityNotification): Boolean =
                oldItem.id == newItem.id

            override fun areContentsTheSame(oldItem: CommunityNotification, newItem: CommunityNotification): Boolean =
                oldItem == newItem
        }
    }
}
