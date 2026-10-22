package com.fyp.basarattradeinvest.feature.recommendation.list

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemRecommendationCardBinding
import com.fyp.basarattradeinvest.domain.model.recommendations.RecommendationSignal
import com.fyp.basarattradeinvest.domain.model.recommendations.StockRecommendation
import java.util.Locale

class RecommendationsAdapter(
    private val onStockClick: (StockRecommendation) -> Unit
) : ListAdapter<StockRecommendation, RecommendationsAdapter.ViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemRecommendationCardBinding.inflate(
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
        private val binding: ItemRecommendationCardBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: StockRecommendation) {
            binding.tvSymbol.text = item.symbol
            binding.tvSignalBadge.text = item.signal.label

            val context = binding.root.context
            when (item.signal) {
                RecommendationSignal.BUY -> {
                    binding.tvSignalBadge.setBackgroundResource(R.drawable.bg_badge_positive)
                    binding.tvSignalBadge.setTextColor(ContextCompat.getColor(context, R.color.color_positive))
                }
                RecommendationSignal.SELL -> {
                    binding.tvSignalBadge.setBackgroundResource(R.drawable.bg_badge_negative)
                    binding.tvSignalBadge.setTextColor(ContextCompat.getColor(context, R.color.color_negative))
                }
                RecommendationSignal.HOLD -> {
                    binding.tvSignalBadge.setBackgroundResource(R.drawable.bg_badge_neutral)
                    binding.tvSignalBadge.setTextColor(ContextCompat.getColor(context, R.color.color_neutral))
                }
            }

            val sign = if (item.compositeScore >= 0) "+" else ""
            binding.tvConfidence.text = String.format(
                Locale.US,
                "Score: %s%.2f (%d%%)",
                sign,
                item.compositeScore,
                (item.confidence * 100).toInt()
            )

            binding.tvSummary.text = item.summary

            if (item.targetPrice != null) {
                binding.tvTargetPrice.text = String.format(Locale.US, "PKR %.2f", item.targetPrice)
            } else {
                binding.tvTargetPrice.text = "N/A"
            }

            if (item.stopLoss != null) {
                binding.tvStopLoss.text = String.format(Locale.US, "PKR %.2f", item.stopLoss)
            } else {
                binding.tvStopLoss.text = "N/A"
            }

            binding.root.setOnClickListener {
                onStockClick(item)
            }
        }
    }

    companion object DiffCallback : DiffUtil.ItemCallback<StockRecommendation>() {
        override fun areItemsTheSame(oldItem: StockRecommendation, newItem: StockRecommendation): Boolean {
            return oldItem.symbol == newItem.symbol
        }

        override fun areContentsTheSame(oldItem: StockRecommendation, newItem: StockRecommendation): Boolean {
            return oldItem == newItem
        }
    }
}
