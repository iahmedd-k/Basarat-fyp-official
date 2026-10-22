package com.fyp.basarattradeinvest.feature.stock.detail.adapter

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemStockTradeBinding
import com.fyp.basarattradeinvest.domain.model.stock.StockTrade
import java.util.Locale

class TradeAdapter : ListAdapter<StockTrade, TradeAdapter.TradeViewHolder>(TradeDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TradeViewHolder {
        val binding = ItemStockTradeBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return TradeViewHolder(binding)
    }

    override fun onBindViewHolder(holder: TradeViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class TradeViewHolder(
        private val binding: ItemStockTradeBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(trade: StockTrade) {
            val ctx = binding.root.context
            binding.tvTradeTime.text = trade.time
            binding.tvTradePrice.text = String.format(Locale.US, "%.2f", trade.price)
            binding.tvTradeVolume.text = String.format(Locale.US, "%,d", trade.volume)
            binding.tvTradeType.text = trade.type

            val color = if (trade.type == "BUY") R.color.color_positive else R.color.color_negative
            binding.tvTradeType.setTextColor(ContextCompat.getColor(ctx, color))
        }
    }

    class TradeDiffCallback : DiffUtil.ItemCallback<StockTrade>() {
        override fun areItemsTheSame(oldItem: StockTrade, newItem: StockTrade): Boolean {
            return oldItem.time == newItem.time && oldItem.price == newItem.price
        }
        override fun areContentsTheSame(oldItem: StockTrade, newItem: StockTrade): Boolean {
            return oldItem == newItem
        }
    }
}
