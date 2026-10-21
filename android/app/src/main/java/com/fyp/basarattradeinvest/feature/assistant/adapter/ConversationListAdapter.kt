package com.fyp.basarattradeinvest.feature.assistant.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantConversation

/**
 * RecyclerView adapter for the conversation list.
 */
class ConversationListAdapter(
    private val onConversationClick: (AssistantConversation) -> Unit,
    private val onDeleteClick: (AssistantConversation) -> Unit
) : ListAdapter<AssistantConversation, ConversationListAdapter.ConversationViewHolder>(DIFF_CALLBACK) {

    companion object {
        private val DIFF_CALLBACK = object : DiffUtil.ItemCallback<AssistantConversation>() {
            override fun areItemsTheSame(oldItem: AssistantConversation, newItem: AssistantConversation): Boolean {
                return oldItem.id == newItem.id
            }

            override fun areContentsTheSame(oldItem: AssistantConversation, newItem: AssistantConversation): Boolean {
                return oldItem == newItem
            }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ConversationViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_conversation, parent, false)
        return ConversationViewHolder(view)
    }

    override fun onBindViewHolder(holder: ConversationViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class ConversationViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvTitle: TextView = itemView.findViewById(R.id.tvConversationTitle)
        private val tvDate: TextView = itemView.findViewById(R.id.tvConversationDate)
        private val btnDelete: ImageButton = itemView.findViewById(R.id.btnDeleteConversation)

        fun bind(conversation: AssistantConversation) {
            tvTitle.text = conversation.title ?: "New Conversation"
            tvDate.text = formatDate(conversation.updatedAt)

            itemView.setOnClickListener { onConversationClick(conversation) }
            btnDelete.setOnClickListener { onDeleteClick(conversation) }
        }

        // Built once per recycled holder; binds ran these on the UI thread only.
        private val isoParser = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", java.util.Locale.US).apply {
            timeZone = java.util.TimeZone.getTimeZone("UTC")
        }
        private val displayFormatter = java.text.SimpleDateFormat("MMM d, hh:mm a", java.util.Locale.US)

        private fun formatDate(isoTimestamp: String): String {
            return try {
                val date = isoParser.parse(isoTimestamp.take(19)) ?: return ""
                displayFormatter.format(date)
            } catch (e: Exception) {
                ""
            }
        }
    }
}
