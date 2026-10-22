package com.fyp.basarattradeinvest.feature.assistant.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.feature.assistant.ChatMessageItem

/**
 * RecyclerView adapter for chat messages.
 * Uses ListAdapter with DiffUtil for efficient updates during streaming.
 */
class ChatMessageAdapter : ListAdapter<ChatMessageItem, RecyclerView.ViewHolder>(DIFF_CALLBACK) {

    companion object {
        private const val VIEW_TYPE_USER = 0
        private const val VIEW_TYPE_ASSISTANT = 1

        private val DIFF_CALLBACK = object : DiffUtil.ItemCallback<ChatMessageItem>() {
            override fun areItemsTheSame(oldItem: ChatMessageItem, newItem: ChatMessageItem): Boolean {
                return oldItem.id == newItem.id
            }

            override fun areContentsTheSame(oldItem: ChatMessageItem, newItem: ChatMessageItem): Boolean {
                return oldItem == newItem
            }
        }
    }

    override fun getItemViewType(position: Int): Int {
        return if (getItem(position).isUser) VIEW_TYPE_USER else VIEW_TYPE_ASSISTANT
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inflater = LayoutInflater.from(parent.context)
        return if (viewType == VIEW_TYPE_USER) {
            UserMessageViewHolder(inflater.inflate(R.layout.item_chat_message_user, parent, false))
        } else {
            AssistantMessageViewHolder(inflater.inflate(R.layout.item_chat_message_assistant, parent, false))
        }
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        val item = getItem(position)
        when (holder) {
            is UserMessageViewHolder -> holder.bind(item)
            is AssistantMessageViewHolder -> holder.bind(item)
        }
    }

    class UserMessageViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvContent: TextView = itemView.findViewById(R.id.tvUserMessage)
        private val tvTimestamp: TextView = itemView.findViewById(R.id.tvUserTimestamp)

        fun bind(item: ChatMessageItem) {
            tvContent.text = item.content
            tvTimestamp.text = formatTimestamp(item.timestamp)
        }
    }

    class AssistantMessageViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvContent: TextView = itemView.findViewById(R.id.tvAssistantMessage)
        private val tvTimestamp: TextView = itemView.findViewById(R.id.tvAssistantTimestamp)
        private val streamingIndicator: View = itemView.findViewById(R.id.streamingIndicator)

        fun bind(item: ChatMessageItem) {
            if (item.content.isEmpty() && item.isStreaming) {
                tvContent.text = "Analyzing market data..."
                tvContent.alpha = 0.6f
            } else {
                tvContent.text = com.fyp.basarattradeinvest.feature.assistant.AssistantMarkdownFormatter.format(item.content)
                tvContent.alpha = 1.0f
            }
            tvTimestamp.text = formatTimestamp(item.timestamp)
            streamingIndicator.visibility = if (item.isStreaming) View.VISIBLE else View.GONE
        }
    }
}

/**
 * Format ISO timestamp to a user-friendly time string.
 */
private val ISO_UTC_PARSER = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", java.util.Locale.US).apply {
    timeZone = java.util.TimeZone.getTimeZone("UTC")
}
private val TIME_OF_DAY_FORMATTER = java.text.SimpleDateFormat("hh:mm a", java.util.Locale.US)

private fun formatTimestamp(isoTimestamp: String): String {
    return try {
        val date = ISO_UTC_PARSER.parse(isoTimestamp.take(19)) ?: return ""
        TIME_OF_DAY_FORMATTER.format(date)
    } catch (e: Exception) {
        ""
    }
}
