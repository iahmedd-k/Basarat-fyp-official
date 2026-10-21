package com.fyp.basarattradeinvest.feature.community.admin.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemModerationActionBinding
import com.fyp.basarattradeinvest.domain.model.community.ModerationAction

class ModerationActionsAdapter :
    ListAdapter<ModerationAction, ModerationActionsAdapter.ActionViewHolder>(ActionDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ActionViewHolder {
        val binding = ItemModerationActionBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return ActionViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ActionViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class ActionViewHolder(
        private val binding: ItemModerationActionBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(action: ModerationAction) {
            val context = binding.root.context
            binding.tvActionBadge.text = action.action.uppercase()

            if (action.action.contains("DELETE", ignoreCase = true) || action.action.contains("REMOVE", ignoreCase = true)) {
                binding.tvActionBadge.setTextColor(ContextCompat.getColor(context, R.color.color_negative))
                binding.tvActionBadge.setBackgroundResource(R.drawable.bg_badge_negative)
            } else if (action.action.contains("RESTORE", ignoreCase = true) || action.action.contains("REVIEW", ignoreCase = true)) {
                binding.tvActionBadge.setTextColor(ContextCompat.getColor(context, R.color.color_positive))
                binding.tvActionBadge.setBackgroundResource(R.drawable.bg_badge_positive)
            } else {
                binding.tvActionBadge.setTextColor(ContextCompat.getColor(context, R.color.color_text_primary))
                binding.tvActionBadge.setBackgroundResource(R.drawable.bg_badge_neutral)
            }

            val modText = if (!action.moderatorUsername.isNullOrBlank()) {
                "Mod: @${action.moderatorUsername}"
            } else if (!action.moderatorId.isNullOrBlank()) {
                "Mod ID: ${action.moderatorId.take(8)}"
            } else {
                "Moderator Action"
            }
            binding.tvModeratorName.text = modText

            binding.tvActionTimestamp.text = formatTimestamp(action.createdAt)

            val targetDetails = buildString {
                if (!action.postId.isNullOrBlank()) append("Post #${action.postId.take(10)} ")
                if (!action.commentId.isNullOrBlank()) append("Comment #${action.commentId.take(10)} ")
                if (!action.reportId.isNullOrBlank()) append("Report #${action.reportId.take(10)}")
                if (isEmpty()) append("Community Content")
            }
            binding.tvActionTarget.text = "Target: $targetDetails"

            val reasonText = if (!action.reason.isNullOrBlank()) {
                "Reason: ${action.reason}"
            } else if (!action.details.isNullOrBlank()) {
                "Details: ${action.details}"
            } else {
                "Policy compliance enforcement"
            }
            binding.tvActionReason.text = reasonText
        }

        private fun formatTimestamp(iso: String): String {
            return if (iso.length >= 16) iso.substring(0, 16).replace("T", " ") else iso
        }
    }

    class ActionDiffCallback : DiffUtil.ItemCallback<ModerationAction>() {
        override fun areItemsTheSame(oldItem: ModerationAction, newItem: ModerationAction): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: ModerationAction, newItem: ModerationAction): Boolean {
            return oldItem == newItem
        }
    }
}
