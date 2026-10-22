package com.fyp.basarattradeinvest.feature.community.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemCommunityUserBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityUserSummary

class CommunityUserAdapter(
    private val onUserClick: (CommunityUserSummary) -> Unit
) : ListAdapter<CommunityUserSummary, CommunityUserAdapter.UserViewHolder>(UserDiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): UserViewHolder {
        val binding = ItemCommunityUserBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return UserViewHolder(binding)
    }

    override fun onBindViewHolder(holder: UserViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class UserViewHolder(private val binding: ItemCommunityUserBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(user: CommunityUserSummary) {
            binding.tvUserName.text = user.displayName
            binding.tvUsername.text = "@${user.username}"

            binding.root.setOnClickListener {
                onUserClick(user)
            }
        }
    }

    companion object {
        private val UserDiffCallback = object : DiffUtil.ItemCallback<CommunityUserSummary>() {
            override fun areItemsTheSame(oldItem: CommunityUserSummary, newItem: CommunityUserSummary): Boolean =
                oldItem.id == newItem.id

            override fun areContentsTheSame(oldItem: CommunityUserSummary, newItem: CommunityUserSummary): Boolean =
                oldItem == newItem
        }
    }
}
