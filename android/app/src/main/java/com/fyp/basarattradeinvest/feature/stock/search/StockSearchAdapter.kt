package com.fyp.basarattradeinvest.feature.stock.search

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.databinding.ItemStockSearchResultBinding
import com.fyp.basarattradeinvest.domain.model.stock.StockSearchResult

class StockSearchAdapter(
    private val onStockClick: (StockSearchResult) -> Unit
) : ListAdapter<StockSearchResult, StockSearchAdapter.StockSearchViewHolder>(DiffCallback) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): StockSearchViewHolder {
        val binding = ItemStockSearchResultBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return StockSearchViewHolder(binding)
    }

    override fun onBindViewHolder(holder: StockSearchViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class StockSearchViewHolder(
        private val binding: ItemStockSearchResultBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: StockSearchResult) {
            binding.tvSymbol.text = item.symbol
            binding.tvName.text = item.name
            binding.tvSector.text = item.sector
            binding.tvSymbolLetter.text = item.symbol.take(1).uppercase()

            binding.root.setOnClickListener {
                onStockClick(item)
            }
        }
    }

    companion object DiffCallback : DiffUtil.ItemCallback<StockSearchResult>() {
        override fun areItemsTheSame(oldItem: StockSearchResult, newItem: StockSearchResult): Boolean {
            return oldItem.symbol == newItem.symbol
        }

        override fun areContentsTheSame(oldItem: StockSearchResult, newItem: StockSearchResult): Boolean {
            return oldItem == newItem
        }
    }
}
