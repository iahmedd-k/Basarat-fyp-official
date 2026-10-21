package com.fyp.basarattradeinvest.feature.community.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemCommunityPostBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost

class CommunityPostAdapter(
    private val onPostClick: ((CommunityPost) -> Unit)? = null,
    private val onLikeClick: ((CommunityPost) -> Unit)? = null,
    private val onCommentClick: ((CommunityPost) -> Unit)? = null
) : ListAdapter<CommunityPost, CommunityPostAdapter.PostViewHolder>(PostDiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): PostViewHolder {
        val binding = ItemCommunityPostBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return PostViewHolder(binding)
    }

    override fun onBindViewHolder(holder: PostViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class PostViewHolder(private val binding: ItemCommunityPostBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(post: CommunityPost) {
            val context = binding.root.context

            // Post content
            binding.tvPostContent.text = post.content

            // Stock symbol badge
            if (!post.stockSymbol.isNullOrBlank()) {
                binding.tvStockBadge.visibility = View.VISIBLE
                binding.tvStockBadge.text = post.stockSymbol
            } else {
                binding.tvStockBadge.visibility = View.GONE
            }

            // Post author & time
            binding.tvPostAuthor.text = post.authorDisplayName
            binding.tvPostTime.text = formatPostTime(post.createdAt)

            // Post image
            if (!post.imageUrl.isNullOrBlank()) {
                binding.ivPostImage.visibility = View.VISIBLE
                com.fyp.basarattradeinvest.core.ui.ImageLoader.loadImage(binding.ivPostImage, post.imageUrl)
            } else {
                binding.ivPostImage.visibility = View.GONE
            }

            // Likes and comments
            binding.tvLikeCount.text = post.likeCount.toString()
            binding.tvCommentCount.text = post.commentCount.toString()

            if (post.likedByMe) {
                binding.ivLikeIcon.setColorFilter(ContextCompat.getColor(context, R.color.color_brand_primary))
                binding.tvLikeCount.setTextColor(ContextCompat.getColor(context, R.color.color_brand_primary))
            } else {
                binding.ivLikeIcon.setColorFilter(ContextCompat.getColor(context, R.color.color_text_secondary))
                binding.tvLikeCount.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
            }

            // Like click
            binding.layoutLikes.setOnClickListener {
                onLikeClick?.invoke(post)
            }

            // Comment click
            binding.layoutComments.setOnClickListener {
                onCommentClick?.invoke(post)
            }

            // Whole item click
            binding.root.setOnClickListener {
                onPostClick?.invoke(post)
            }
        }

        private fun formatPostTime(rawIso: String): String {
            return try {
                if (rawIso.length >= 10) rawIso.substring(0, 10) else rawIso
            } catch (e: Exception) {
                rawIso
            }
        }
    }

    companion object {
        private val PostDiffCallback = object : DiffUtil.ItemCallback<CommunityPost>() {
            override fun areItemsTheSame(oldItem: CommunityPost, newItem: CommunityPost): Boolean =
                oldItem.id == newItem.id

            override fun areContentsTheSame(oldItem: CommunityPost, newItem: CommunityPost): Boolean =
                oldItem == newItem
        }
    }
}
