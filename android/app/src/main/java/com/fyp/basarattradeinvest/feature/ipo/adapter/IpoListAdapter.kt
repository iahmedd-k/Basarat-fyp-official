package com.fyp.basarattradeinvest.feature.ipo.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemIpoCardBinding
import com.fyp.basarattradeinvest.domain.model.ipo.IpoItem
import com.fyp.basarattradeinvest.feature.common.FormatUtils

class IpoListAdapter(
    private val onItemClick: (IpoItem) -> Unit = {}
) : ListAdapter<IpoItem, IpoListAdapter.IpoViewHolder>(DiffCallback) {

    inner class IpoViewHolder(
        private val binding: ItemIpoCardBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: IpoItem) {
            val context = binding.root.context

            binding.tvIpoSymbol.text = item.symbol
            binding.tvIpoCompany.text = item.companyName

            if (item.sector.isNullOrBlank()) {
                binding.tvIpoSector.visibility = View.GONE
            } else {
                binding.tvIpoSector.visibility = View.VISIBLE
                binding.tvIpoSector.text = item.sector
            }

            // Status badge
            binding.tvIpoStatus.text = FormatUtils.ipoStatus(item.status)
            val (badgeBg, badgeColor) = statusBadge(item.status)
            binding.tvIpoStatus.setBackgroundResource(badgeBg)
            binding.tvIpoStatus.setTextColor(ContextCompat.getColor(context, badgeColor))

            // Floor price — never render 0.00 for a missing value
            if (item.floorPrice == null) {
                binding.tvIpoFloorLabel.visibility = View.GONE
                binding.tvIpoFloorPrice.visibility = View.GONE
            } else {
                binding.tvIpoFloorLabel.visibility = View.VISIBLE
                binding.tvIpoFloorPrice.visibility = View.VISIBLE
                binding.tvIpoFloorPrice.text = FormatUtils.price(item.floorPrice)
            }

            // Shariah compliance
            val shariahVisibility = if (item.isShariahCompliant) View.VISIBLE else View.GONE
            binding.ivIpoShariah.visibility = shariahVisibility
            binding.tvIpoShariah.visibility = shariahVisibility

            // Listing / listed date
            val date = FormatUtils.parseDate(item.listingDate)
            if (date == null) {
                binding.tvIpoListingDate.visibility = View.GONE
            } else {
                binding.tvIpoListingDate.visibility = View.VISIBLE
                val prefix = if (item.status == "LISTED") "Listed" else "Listing"
                binding.tvIpoListingDate.text = "$prefix ${FormatUtils.dateFull(date)}"
            }

            binding.root.setOnClickListener { onItemClick(item) }
        }

        private fun statusBadge(status: String?): Pair<Int, Int> = when (status) {
            "OPEN_FOR_BOOK_BUILDING", "OPEN_FOR_PUBLIC_SUBSCRIPTION" ->
                R.drawable.bg_badge_positive to R.color.color_positive
            "LISTED" ->
                R.drawable.bg_badge_teal to R.color.color_shariah_teal
            else ->
                R.drawable.bg_badge_neutral to R.color.color_neutral
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): IpoViewHolder {
        val binding = ItemIpoCardBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return IpoViewHolder(binding)
    }

    override fun onBindViewHolder(holder: IpoViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    companion object DiffCallback : DiffUtil.ItemCallback<IpoItem>() {
        override fun areItemsTheSame(oldItem: IpoItem, newItem: IpoItem): Boolean =
            oldItem.symbol == newItem.symbol && oldItem.id == newItem.id

        override fun areContentsTheSame(oldItem: IpoItem, newItem: IpoItem): Boolean =
            oldItem == newItem
    }
}
