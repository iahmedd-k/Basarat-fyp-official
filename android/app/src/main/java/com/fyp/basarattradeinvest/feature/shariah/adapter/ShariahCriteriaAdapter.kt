package com.fyp.basarattradeinvest.feature.shariah.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemShariahCriterionBinding
import com.fyp.basarattradeinvest.domain.model.shariah.ShariahCriterionItem
import java.util.Locale

class ShariahCriteriaAdapter : ListAdapter<ShariahCriterionItem, ShariahCriteriaAdapter.CriterionViewHolder>(CriterionDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): CriterionViewHolder {
        val binding = ItemShariahCriterionBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return CriterionViewHolder(binding)
    }

    override fun onBindViewHolder(holder: CriterionViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    inner class CriterionViewHolder(
        private val binding: ItemShariahCriterionBinding
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(item: ShariahCriterionItem) {
            val context = binding.root.context

            binding.tvCriterionName.text = item.name
            val detail = listOfNotNull(item.description?.takeIf { it.isNotBlank() }, item.exception)
                .joinToString(" ")
                .takeIf { it.isNotBlank() }
            binding.tvCriterionDescription.visibility = if (detail == null) View.GONE else View.VISIBLE
            binding.tvCriterionDescription.text = detail.orEmpty()

            when (item.passed) {
                true -> {
                    binding.tvCriterionStatusBadge.text = "PASSED ✓"
                    binding.tvCriterionStatusBadge.setBackgroundResource(R.drawable.bg_badge_shariah_compliant)
                    binding.tvCriterionStatusBadge.setTextColor(ContextCompat.getColor(context, R.color.color_shariah_teal))
                }
                false -> {
                    binding.tvCriterionStatusBadge.text = "FAILED ✗"
                    binding.tvCriterionStatusBadge.setBackgroundResource(R.drawable.bg_badge_shariah_non_compliant)
                    binding.tvCriterionStatusBadge.setTextColor(ContextCompat.getColor(context, R.color.color_negative))
                }
                null -> {
                    binding.tvCriterionStatusBadge.text = UNAVAILABLE
                    binding.tvCriterionStatusBadge.setBackgroundResource(R.drawable.bg_badge_shariah_non_compliant)
                    binding.tvCriterionStatusBadge.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))
                }
            }

            val measuredValStr = if (item.name.contains("Core", ignoreCase = true)) {
                when (item.passed) {
                    true -> "Compliant"
                    false -> "Non-Compliant"
                    null -> UNAVAILABLE
                }
            } else if (item.value != null) {
                String.format(Locale.US, "%.2f%%", item.value)
            } else {
                UNAVAILABLE
            }
            binding.tvCriterionMeasuredValue.text = measuredValStr

            val threshold = item.threshold
            binding.tvCriterionThresholdValue.text = when {
                item.name.contains("Core", ignoreCase = true) -> "Halal Only"
                threshold != null -> String.format(Locale.US, "≤ %.2f%%", threshold)
                else -> UNAVAILABLE
            }
        }
    }

    class CriterionDiffCallback : DiffUtil.ItemCallback<ShariahCriterionItem>() {
        override fun areItemsTheSame(oldItem: ShariahCriterionItem, newItem: ShariahCriterionItem): Boolean {
            return oldItem.name == newItem.name
        }

        override fun areContentsTheSame(oldItem: ShariahCriterionItem, newItem: ShariahCriterionItem): Boolean {
            return oldItem == newItem
        }
    }

    companion object {
        private const val UNAVAILABLE = "—"
    }
}
