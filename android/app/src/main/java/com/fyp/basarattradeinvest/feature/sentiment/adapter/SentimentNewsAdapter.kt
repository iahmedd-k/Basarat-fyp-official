package com.fyp.basarattradeinvest.feature.sentiment.adapter

import android.content.Intent
import android.net.Uri
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.domain.model.sentiment.SentimentNewsItem

/**
 * SentimentNewsAdapter
 *
 * RecyclerView adapter for sentiment-annotated news articles.
 * Uses ListAdapter + DiffUtil for efficient updates and append (pagination).
 *
 * Rendered fields (only from actual API response):
 *   - title (required)
 *   - source (nullable — shown if not null)
 *   - published_at (nullable — shown if not null)
 *   - sentiment (nullable — colored badge if not null)
 *   - sentiment_score (nullable — shown if not null)
 *   - url (nullable — opens browser if tapped, only when not null)
 *
 * No image view — API does not return an image field.
 */
class SentimentNewsAdapter : ListAdapter<SentimentNewsItem, SentimentNewsAdapter.NewsViewHolder>(DIFF_CALLBACK) {

    companion object {
        private val DIFF_CALLBACK = object : DiffUtil.ItemCallback<SentimentNewsItem>() {
            override fun areItemsTheSame(oldItem: SentimentNewsItem, newItem: SentimentNewsItem): Boolean =
                oldItem.id == newItem.id

            override fun areContentsTheSame(oldItem: SentimentNewsItem, newItem: SentimentNewsItem): Boolean =
                oldItem == newItem
        }
    }

    inner class NewsViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        val tvTitle: TextView = itemView.findViewById(R.id.tv_news_title)
        val tvSourceDate: TextView = itemView.findViewById(R.id.tv_news_source_date)
        val tvSentimentBadge: TextView = itemView.findViewById(R.id.tv_news_sentiment_badge)
        val tvSentimentScore: TextView = itemView.findViewById(R.id.tv_news_sentiment_score)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): NewsViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_sentiment_news, parent, false)
        return NewsViewHolder(view)
    }

    override fun onBindViewHolder(holder: NewsViewHolder, position: Int) {
        val item = getItem(position)
        val ctx = holder.itemView.context

        // Title (always present — required field)
        holder.tvTitle.text = item.title

        // Source · Date (both nullable)
        val parts = buildList {
            item.source?.let { add(it) }
            item.publishedAt?.let { add(formatDate(it)) }
        }
        if (parts.isNotEmpty()) {
            holder.tvSourceDate.text = parts.joinToString(" · ")
            holder.tvSourceDate.visibility = View.VISIBLE
        } else {
            holder.tvSourceDate.visibility = View.GONE
        }

        // Sentiment badge (nullable — API returns POSITIVE/NEGATIVE/NEUTRAL or lowercase)
        if (!item.sentiment.isNullOrBlank()) {
            holder.tvSentimentBadge.visibility = View.VISIBLE
            val label = item.sentiment.uppercase()
            holder.tvSentimentBadge.text = label

            val (bgRes, colorRes) = when {
                label.contains("POSITIVE") || label.contains("BULLISH") -> Pair(R.drawable.bg_badge_positive, R.color.color_positive)
                label.contains("NEGATIVE") || label.contains("BEARISH") -> Pair(R.drawable.bg_badge_negative, R.color.color_negative)
                else -> Pair(R.drawable.bg_badge_neutral, R.color.color_text_secondary)
            }
            holder.tvSentimentBadge.setBackgroundResource(bgRes)
            holder.tvSentimentBadge.setTextColor(ContextCompat.getColor(ctx, colorRes))
        } else {
            holder.tvSentimentBadge.visibility = View.GONE
        }

        // Sentiment score (nullable — scale is -1.0 to +1.0)
        if (item.sentimentScore != null) {
            holder.tvSentimentScore.visibility = View.VISIBLE
            holder.tvSentimentScore.text = String.format("Score: %+.2f", item.sentimentScore)
        } else {
            holder.tvSentimentScore.visibility = View.GONE
        }

        // Click → open URL in browser (only if url is not null)
        if (!item.url.isNullOrBlank()) {
            holder.itemView.setOnClickListener {
                try {
                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(item.url))
                    ctx.startActivity(intent)
                } catch (e: Exception) {
                    // URL could not be opened — silently ignore
                }
            }
        } else {
            holder.itemView.setOnClickListener(null)
            holder.itemView.isClickable = false
        }
    }

    /**
     * Formats published_at string for display.
     * API returns ISO-like timestamps or date strings.
     * We show the date portion only (first 10 chars: YYYY-MM-DD).
     */
    private fun formatDate(raw: String): String {
        return if (raw.length >= 10) raw.substring(0, 10) else raw
    }
}
