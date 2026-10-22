package com.fyp.basarattradeinvest.feature.community.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemCommunityCommentBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityComment

class CommunityCommentsAdapter : ListAdapter<CommunityComment, CommunityCommentsAdapter.CommentViewHolder>(CommentDiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): CommentViewHolder {
        val binding = ItemCommunityCommentBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return CommentViewHolder(binding)
    }

    override fun onBindViewHolder(holder: CommentViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class CommentViewHolder(private val binding: ItemCommunityCommentBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(comment: CommunityComment) {
            binding.tvCommentAuthor.text = comment.authorDisplayName
            binding.tvCommentContent.text = comment.content
            binding.tvCommentTime.text = formatTime(comment.createdAt)
        }

        private fun formatTime(rawIso: String): String {
            return try {
                if (rawIso.length >= 10) rawIso.substring(0, 10) else rawIso
            } catch (e: Exception) {
                rawIso
            }
        }
    }

    companion object {
        private val CommentDiffCallback = object : DiffUtil.ItemCallback<CommunityComment>() {
            override fun areItemsTheSame(oldItem: CommunityComment, newItem: CommunityComment): Boolean =
                oldItem.id == newItem.id

            override fun areContentsTheSame(oldItem: CommunityComment, newItem: CommunityComment): Boolean =
                oldItem == newItem
        }
    }
}
