package com.fyp.basarattradeinvest.feature.community.admin.adapter

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.ItemAdminReportBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityReport
import com.fyp.basarattradeinvest.domain.model.community.ReportStatusEnum

class AdminReportsAdapter(
    private val onReportClick: (CommunityReport) -> Unit
) : ListAdapter<CommunityReport, AdminReportsAdapter.ReportViewHolder>(ReportDiffCallback()) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ReportViewHolder {
        val binding = ItemAdminReportBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return ReportViewHolder(binding, onReportClick)
    }

    override fun onBindViewHolder(holder: ReportViewHolder, position: Int) {
        holder.bind(getItem(position))
    }

    class ReportViewHolder(
        private val binding: ItemAdminReportBinding,
        private val onReportClick: (CommunityReport) -> Unit
    ) : RecyclerView.ViewHolder(binding.root) {

        fun bind(report: CommunityReport) {
            val context = binding.root.context

            binding.tvTargetType.text = report.targetTypeLabel.uppercase()
            binding.tvTargetId.text = if (report.isPostReport) "#${report.postId}" else if (report.isCommentReport) "#${report.commentId}" else "#${report.id}"
            binding.tvReportReason.text = "Reason: ${report.reason}"

            if (!report.targetContent.isNullOrBlank()) {
                binding.tvContentPreview.visibility = View.VISIBLE
                binding.tvContentPreview.text = report.targetContent
            } else {
                binding.tvContentPreview.visibility = View.GONE
            }

            val reporterText = if (!report.reporterUsername.isNullOrBlank()) {
                "Reported by @${report.reporterUsername}"
            } else if (!report.reporterId.isNullOrBlank()) {
                "Reporter ID: ${report.reporterId}"
            } else {
                "Reported anonymously"
            }
            binding.tvReporterInfo.text = reporterText

            binding.tvReportDate.text = formatTimestamp(report.createdAt)

            // Status Badge styling
            binding.tvReportStatus.text = report.status.value
            when (report.status) {
                ReportStatusEnum.PENDING -> {
                    binding.tvReportStatus.setTextColor(ContextCompat.getColor(context, R.color.color_gold_accent))
                    binding.tvReportStatus.setBackgroundResource(R.drawable.bg_badge_neutral)
                }
                ReportStatusEnum.REVIEWED -> {
                    binding.tvReportStatus.setTextColor(ContextCompat.getColor(context, R.color.color_positive))
                    binding.tvReportStatus.setBackgroundResource(R.drawable.bg_badge_positive)
                }
                ReportStatusEnum.DISMISSED -> {
                    binding.tvReportStatus.setTextColor(ContextCompat.getColor(context, R.color.color_text_tertiary))
                    binding.tvReportStatus.setBackgroundResource(R.drawable.bg_badge_neutral)
                }
            }

            binding.root.setOnClickListener {
                onReportClick(report)
            }
        }

        private fun formatTimestamp(iso: String): String {
            return if (iso.length >= 10) iso.substring(0, 10) else iso
        }
    }

    class ReportDiffCallback : DiffUtil.ItemCallback<CommunityReport>() {
        override fun areItemsTheSame(oldItem: CommunityReport, newItem: CommunityReport): Boolean {
            return oldItem.id == newItem.id
        }

        override fun areContentsTheSame(oldItem: CommunityReport, newItem: CommunityReport): Boolean {
            return oldItem == newItem
        }
    }
}
