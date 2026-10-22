package com.fyp.basarattradeinvest.feature.news.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemNewsArticleBinding
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import java.util.Locale

class NewsArticleAdapter(
    private val onArticleClick: (NewsArticle) -> Unit = {}
) : ListAdapter<NewsArticle, NewsArticleAdapter.NewsViewHolder>(NewsDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): NewsViewHolder {
        val binding = ItemNewsArticleBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return NewsViewHolder(binding)
    }

    override fun onBindViewHolder(holder: NewsViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class NewsViewHolder(
        private val binding: ItemNewsArticleBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: NewsArticle) {
            val context = binding.root.context

            binding.tvNewsTicker.text = item.symbol
            binding.tvDividendBadge.visibility = if (item.hasDividend) View.VISIBLE else View.GONE
            binding.tvNewsSource.text = if (item.isOfficial) "${item.source} • Official" else item.source
            binding.tvNewsTime.text = item.timestamp

            // Sentiment is intentionally hidden in the generic news feed.
            // Use dedicated stock/portfolio sentiment screens for sentiment analysis.
            binding.tvNewsSentiment.visibility = View.GONE
            binding.tvNewsSentiment.text = ""

            binding.tvNewsHeadline.text = item.headline
            binding.tvNewsSnippet.text = item.snippet

            binding.root.setOnClickListener {
                onArticleClick(item)
            }
        }
    }

    class NewsDiffCallback : DiffUtil.ItemCallback<NewsArticle>() {
        override fun areItemsTheSame(oldItem: NewsArticle, newItem: NewsArticle): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: NewsArticle, newItem: NewsArticle): Boolean {
            return oldItem == newItem
        }
    }
}
