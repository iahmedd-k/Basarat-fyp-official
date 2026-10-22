package com.fyp.basarattradeinvest.feature.community.admin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentAdminReportDetailBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.launch

class AdminReportDetailFragment : Fragment() {

    private var _binding: FragmentAdminReportDetailBinding? = null
    private val binding get() = _binding!!

    private val viewModel: AdminCommunityViewModel by viewModels()

    private var reportId: String = ""
    private var postId: String? = null
    private var commentId: String? = null
    private var reportReason: String = ""
    private var reporterInfo: String = ""
    private var reportStatus: String = "PENDING"
    private var targetContent: String? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentAdminReportDetailBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        extractArguments()
        bindReportDetails()
        setupListeners()
        observePostReview()

        // If this report targets a post, fetch the latest post details from the admin review endpoint
        postId?.let { id ->
            if (id.isNotBlank()) {
                viewModel.loadAdminPost(id)
            }
        }
    }

    private fun extractArguments() {
        arguments?.let {
            reportId = it.getString("report_id", "")
            postId = it.getString("post_id")
            commentId = it.getString("comment_id")
            reportReason = it.getString("reason", "")
            reporterInfo = it.getString("reporter", "")
            reportStatus = it.getString("status", "PENDING")
            targetContent = it.getString("target_content")
        }
    }

    private fun bindReportDetails() {
        binding.tvReportId.text = reportId.ifEmpty { "N/A" }
        binding.tvHeaderStatus.text = reportStatus.uppercase()
        updateStatusBadge(reportStatus)

        val targetTypeStr = if (!postId.isNullOrBlank()) "Post (#$postId)" else if (!commentId.isNullOrBlank()) "Comment (#$commentId)" else "Content"
        binding.tvTargetTypeDesc.text = targetTypeStr

        binding.tvReporterDesc.text = if (reporterInfo.isNotBlank()) "@$reporterInfo" else "Anonymous"
        binding.tvReasonDesc.text = reportReason.ifEmpty { "No reason provided" }

        if (!targetContent.isNullOrBlank()) {
            binding.tvContentBody.text = targetContent
        } else {
            binding.tvContentBody.text = "Loading content details..."
        }

        // Configure visibility of action buttons
        val hasComment = !commentId.isNullOrBlank()
        binding.btnDeleteComment.visibility = if (hasComment) View.VISIBLE else View.GONE

        val hasPost = !postId.isNullOrBlank()
        binding.btnRestorePost.visibility = if (hasPost) View.VISIBLE else View.GONE
        binding.btnRemovePost.visibility = if (hasPost) View.VISIBLE else View.GONE
        binding.btnDeletePost.visibility = if (hasPost) View.VISIBLE else View.GONE
    }

    private fun updateStatusBadge(status: String) {
        when (status.uppercase()) {
            "REVIEWED" -> {
                binding.tvHeaderStatus.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))
                binding.tvHeaderStatus.setBackgroundResource(R.drawable.bg_badge_positive)
            }
            "PENDING" -> {
                binding.tvHeaderStatus.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_gold_accent))
                binding.tvHeaderStatus.setBackgroundResource(R.drawable.bg_badge_neutral)
            }
            "DISMISSED" -> {
                binding.tvHeaderStatus.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_tertiary))
                binding.tvHeaderStatus.setBackgroundResource(R.drawable.bg_badge_neutral)
            }
        }
    }

    private fun setupListeners() {
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        // 1. Report Status: Mark Reviewed
        binding.btnMarkReviewed.setOnClickListener {
            viewModel.updateReportStatus(reportId, "REVIEWED") {
                reportStatus = "REVIEWED"
                binding.tvHeaderStatus.text = "REVIEWED"
                updateStatusBadge("REVIEWED")
            }
        }

        // 2. Report Status: Dismiss Report
        binding.btnDismissReport.setOnClickListener {
            viewModel.updateReportStatus(reportId, "DISMISSED") {
                reportStatus = "DISMISSED"
                binding.tvHeaderStatus.text = "DISMISSED"
                updateStatusBadge("DISMISSED")
            }
        }

        // 3. Destructive Action: Restore Temporarily Hidden Post
        binding.btnRestorePost.setOnClickListener {
            val id = postId ?: return@setOnClickListener
            MaterialAlertDialogBuilder(requireContext())
                .setTitle("Restore Post?")
                .setMessage("This action will restore the temporarily hidden post back to Published status.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Restore") { _, _ ->
                    viewModel.restorePost(id)
                }
                .show()
        }

        // 4. Destructive Action: Direct Remove Post (Moderation)
        binding.btnRemovePost.setOnClickListener {
            val id = postId ?: return@setOnClickListener
            MaterialAlertDialogBuilder(requireContext())
                .setTitle("Direct Remove Post?")
                .setMessage("This action will remove the post from public view under moderation policy. Are you sure?")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Remove Post") { _, _ ->
                    viewModel.removePost(id)
                }
                .show()
        }

        // 5. Destructive Action: Permanently Delete Post
        binding.btnDeletePost.setOnClickListener {
            val id = postId ?: return@setOnClickListener
            MaterialAlertDialogBuilder(requireContext())
                .setTitle("Delete Post?")
                .setMessage("This action will permanently delete this post from the database. Are you sure?")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Permanently Delete") { _, _ ->
                    viewModel.deletePost(id) {
                        findNavController().popBackStack()
                    }
                }
                .show()
        }

        // 6. Destructive Action: Delete Comment
        binding.btnDeleteComment.setOnClickListener {
            val id = commentId ?: return@setOnClickListener
            MaterialAlertDialogBuilder(requireContext())
                .setTitle("Delete Comment?")
                .setMessage("This action will permanently delete this reported comment. Are you sure?")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Delete Comment") { _, _ ->
                    viewModel.deleteComment(id) {
                        findNavController().popBackStack()
                    }
                }
                .show()
        }
    }

    private fun observePostReview() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    viewModel.postReviewUiState.collect { state ->
                        when (state) {
                            is AdminPostReviewUiState.Loading -> {
                                binding.tvPostModerationStatus.text = "LOADING..."
                            }
                            is AdminPostReviewUiState.Success -> {
                                bindPostData(state.post)
                            }
                            is AdminPostReviewUiState.Error -> {
                                binding.tvContentStats.text = "Could not load post details: ${state.message}"
                            }
                            is AdminPostReviewUiState.Idle -> {
                                // Do nothing
                            }
                        }
                    }
                }

                launch {
                    viewModel.userMessage.collect { msg ->
                        Toast.makeText(requireContext(), msg, Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }

    private fun bindPostData(post: CommunityPost) {
        binding.tvContentBody.text = post.content
        binding.tvPostModerationStatus.text = post.status.uppercase()

        when (post.status.uppercase()) {
            "PUBLISHED" -> {
                binding.tvPostModerationStatus.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_positive))
                binding.tvPostModerationStatus.setBackgroundResource(R.drawable.bg_badge_positive)
                binding.btnRestorePost.visibility = View.GONE
                binding.btnRemovePost.visibility = View.VISIBLE
            }
            "TEMPORARILY_HIDDEN" -> {
                binding.tvPostModerationStatus.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_gold_accent))
                binding.tvPostModerationStatus.setBackgroundResource(R.drawable.bg_badge_neutral)
                binding.btnRestorePost.visibility = View.VISIBLE
                binding.btnRemovePost.visibility = View.VISIBLE
            }
            "DELETED" -> {
                binding.tvPostModerationStatus.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_negative))
                binding.tvPostModerationStatus.setBackgroundResource(R.drawable.bg_badge_negative)
                binding.btnRestorePost.visibility = View.GONE
                binding.btnRemovePost.visibility = View.GONE
            }
        }

        binding.tvContentStats.text = buildString {
            append("Author ID: ${post.authorId.take(12)} • ")
            append("Reports: ${post.reportCount} • ")
            append("Likes: ${post.likeCount} • ")
            append("Comments: ${post.commentCount}")
            if (!post.removedReason.isNullOrBlank()) {
                append(" • Removed: ${post.removedReason}")
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
