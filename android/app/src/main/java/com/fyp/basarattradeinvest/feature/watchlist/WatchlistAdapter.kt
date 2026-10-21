package com.fyp.basarattradeinvest.feature.watchlist

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemWatchlistBinding
import com.fyp.basarattradeinvest.domain.model.watchlist.WatchlistItem
import java.text.NumberFormat
import java.util.Locale

class WatchlistAdapter(
    private val onStockClick: (WatchlistItem) -> Unit,
    private val onRemoveClick: (WatchlistItem) -> Unit
) : ListAdapter<WatchlistItem, WatchlistAdapter.ViewHolder>(DiffCallback) {

    private var pendingRemovals: Set<String> = emptySet()

    private val priceFormat = NumberFormat.getNumberInstance(Locale.US).apply {
        minimumFractionDigits = 2
        maximumFractionDigits = 2
    }

    fun submitList(items: List<WatchlistItem>, pendingRemovals: Set<String>) {
        val onlyProgressChanged = items == currentList && this.pendingRemovals != pendingRemovals
        this.pendingRemovals = pendingRemovals
        if (onlyProgressChanged) {
            // The rows are unchanged, so the differ would rebind nothing; the in-flight
            // marker still has to reach the visible hearts.
            notifyItemRangeChanged(0, itemCount)
            return
        }
        super.submitList(items)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemWatchlistBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class ViewHolder(
        private val binding: ItemWatchlistBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: WatchlistItem) {
            val context = binding.root.context

            binding.tvWatchlistSymbol.text = item.symbol
            binding.tvWatchlistName.text = item.name?.takeIf { it.isNotBlank() } ?: item.symbol
            binding.tvWatchlistPrice.text = item.currentPrice?.let(priceFormat::format) ?: "—"

            val changePercent = item.changePercent
            if (changePercent != null) {
                val prefix = if (changePercent >= 0) "+" else ""
                binding.tvWatchlistChange.text =
                    String.format(Locale.US, "%s%.2f%%", prefix, changePercent)
                binding.tvWatchlistChange.setTextColor(
                    ContextCompat.getColor(
                        context,
                        if (changePercent >= 0) R.color.color_positive else R.color.color_negative
                    )
                )
            } else {
                // PSX quotes are delayed/end-of-day; say so instead of implying a live reading.
                binding.tvWatchlistChange.text = if (item.isStale) "Delayed" else "—"
                binding.tvWatchlistChange.setTextColor(
                    ContextCompat.getColor(context, R.color.color_text_tertiary)
                )
            }

            val isRemoving = item.symbol in pendingRemovals
            binding.ivWatchlistFavorite.alpha = if (isRemoving) 0.35f else 1f
            binding.ivWatchlistFavorite.isEnabled = !isRemoving
            binding.ivWatchlistFavorite.contentDescription =
                if (isRemoving) "Removing ${item.symbol} from watchlist"
                else "Remove ${item.symbol} from watchlist"

            binding.root.setOnClickListener { onStockClick(item) }
            binding.ivWatchlistFavorite.setOnClickListener { onRemoveClick(item) }
        }
    }

    companion object DiffCallback : DiffUtil.ItemCallback<WatchlistItem>() {
        override fun areItemsTheSame(oldItem: WatchlistItem, newItem: WatchlistItem): Boolean =
            oldItem.symbol == newItem.symbol

        override fun areContentsTheSame(oldItem: WatchlistItem, newItem: WatchlistItem): Boolean =
            oldItem == newItem
    }
}
