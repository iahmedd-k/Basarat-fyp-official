package com.fyp.basarattradeinvest.feature.community.admin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentAdminCommunityHubBinding
import com.fyp.basarattradeinvest.feature.community.admin.adapter.AdminReportsAdapter
import com.fyp.basarattradeinvest.feature.community.admin.adapter.ModerationActionsAdapter
import kotlinx.coroutines.launch

class AdminCommunityHubFragment : Fragment() {

    private var _binding: FragmentAdminCommunityHubBinding? = null
    private val binding get() = _binding!!

    private val viewModel: AdminCommunityViewModel by viewModels()

    private lateinit var reportsAdapter: AdminReportsAdapter
    private lateinit var actionsAdapter: ModerationActionsAdapter

    private var currentModeIsReports = true

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentAdminCommunityHubBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupRecyclerViews()
        setupListeners()
        observeUiStates()
    }

    private fun setupRecyclerViews() {
        reportsAdapter = AdminReportsAdapter { report ->
            val bundle = Bundle().apply {
                putString("report_id", report.id)
                putString("post_id", report.postId)
                putString("comment_id", report.commentId)
                putString("reason", report.reason)
                putString("reporter", report.reporterUsername ?: report.reporterId)
                putString("status", report.status.value)
                putString("target_content", report.targetContent)
                putString("created_at", report.createdAt)
            }
            findNavController().navigate(R.id.action_adminCommunityHub_to_reportDetail, bundle)
        }
        binding.rvReports.layoutManager = LinearLayoutManager(requireContext())
        binding.rvReports.adapter = reportsAdapter

        actionsAdapter = ModerationActionsAdapter()
        binding.rvAuditLog.layoutManager = LinearLayoutManager(requireContext())
        binding.rvAuditLog.adapter = actionsAdapter
    }

    private fun setupListeners() {
        binding.ivBack.setOnClickListener {
            findNavController().popBackStack()
        }

        binding.ivRefresh.setOnClickListener {
            viewModel.refreshAll()
        }

        binding.swipeReports.setOnRefreshListener {
            viewModel.loadReports()
        }

        binding.swipeAuditLog.setOnRefreshListener {
            viewModel.loadModerationActions()
        }

        // Tab Switching
        binding.tabReports.setOnClickListener {
            switchToReportsMode()
        }

        binding.tabAuditLog.setOnClickListener {
            switchToAuditLogMode()
        }

        // Filter Chips
        binding.chipFilterAll.setOnClickListener {
            updateFilterSelection(ReportStatusFilter.ALL)
        }
        binding.chipFilterPending.setOnClickListener {
            updateFilterSelection(ReportStatusFilter.PENDING)
        }
        binding.chipFilterReviewed.setOnClickListener {
            updateFilterSelection(ReportStatusFilter.REVIEWED)
        }
        binding.chipFilterDismissed.setOnClickListener {
            updateFilterSelection(ReportStatusFilter.DISMISSED)
        }

        binding.btnErrorAction.setOnClickListener {
            viewModel.refreshAll()
        }
    }

    private fun switchToReportsMode() {
        currentModeIsReports = true
        binding.tabReports.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_brand_primary))
        binding.tabReports.setTypeface(null, android.graphics.Typeface.BOLD)
        binding.tabAuditLog.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
        binding.tabAuditLog.setTypeface(null, android.graphics.Typeface.NORMAL)

        binding.scrollFilterChips.visibility = View.VISIBLE
        binding.swipeReports.visibility = View.VISIBLE
        binding.swipeAuditLog.visibility = View.GONE

        // Refresh state rendering for reports
        renderReportsState(viewModel.reportsUiState.value)
    }

    private fun switchToAuditLogMode() {
        currentModeIsReports = false
        binding.tabAuditLog.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_brand_primary))
        binding.tabAuditLog.setTypeface(null, android.graphics.Typeface.BOLD)
        binding.tabReports.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
        binding.tabReports.setTypeface(null, android.graphics.Typeface.NORMAL)

        binding.scrollFilterChips.visibility = View.GONE
        binding.swipeReports.visibility = View.GONE
        binding.swipeAuditLog.visibility = View.VISIBLE

        // Refresh state rendering for actions
        renderActionsState(viewModel.actionsUiState.value)
    }

    private fun updateFilterSelection(filter: ReportStatusFilter) {
        val chips = listOf(
            binding.chipFilterAll to ReportStatusFilter.ALL,
            binding.chipFilterPending to ReportStatusFilter.PENDING,
            binding.chipFilterReviewed to ReportStatusFilter.REVIEWED,
            binding.chipFilterDismissed to ReportStatusFilter.DISMISSED
        )

        chips.forEach { (view, chipFilter) ->
            if (chipFilter == filter) {
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_brand_primary))
                view.setTypeface(null, android.graphics.Typeface.BOLD)
            } else {
                view.setTextColor(ContextCompat.getColor(requireContext(), R.color.color_text_secondary))
                view.setTypeface(null, android.graphics.Typeface.NORMAL)
            }
        }

        viewModel.setFilter(filter)
    }

    private fun observeUiStates() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    viewModel.reportsUiState.collect { state ->
                        if (currentModeIsReports) {
                            renderReportsState(state)
                        }
                    }
                }

                launch {
                    viewModel.actionsUiState.collect { state ->
                        if (!currentModeIsReports) {
                            renderActionsState(state)
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

    private fun renderReportsState(state: AdminReportsUiState) {
        binding.swipeReports.isRefreshing = false

        when (state) {
            is AdminReportsUiState.Loading -> {
                binding.progressBar.visibility = View.VISIBLE
                binding.layoutEmptyState.visibility = View.GONE
                binding.layoutErrorState.visibility = View.GONE
            }
            is AdminReportsUiState.Success -> {
                binding.progressBar.visibility = View.GONE
                binding.layoutEmptyState.visibility = View.GONE
                binding.layoutErrorState.visibility = View.GONE
                reportsAdapter.submitList(state.reports)
            }
            is AdminReportsUiState.Empty -> {
                binding.progressBar.visibility = View.GONE
                binding.layoutEmptyState.visibility = View.VISIBLE
                binding.layoutErrorState.visibility = View.GONE
                binding.tvEmptyTitle.text = "No Reports Found"
                binding.tvEmptyMessage.text = "There are no reports matching this status filter."
                reportsAdapter.submitList(emptyList())
            }
            is AdminReportsUiState.Error -> {
                binding.progressBar.visibility = View.GONE
                binding.layoutEmptyState.visibility = View.GONE
                binding.layoutErrorState.visibility = View.VISIBLE
                if (state.isForbidden) {
                    binding.tvErrorTitle.text = "Access Denied"
                    binding.tvErrorMessage.text = state.message
                    binding.btnErrorAction.visibility = View.GONE
                } else {
                    binding.tvErrorTitle.text = "Unable to Load Reports"
                    binding.tvErrorMessage.text = state.message
                    binding.btnErrorAction.visibility = View.VISIBLE
                }
                reportsAdapter.submitList(emptyList())
            }
        }
    }

    private fun renderActionsState(state: ModerationActionsUiState) {
        binding.swipeAuditLog.isRefreshing = false

        when (state) {
            is ModerationActionsUiState.Loading -> {
                binding.progressBar.visibility = View.VISIBLE
                binding.layoutEmptyState.visibility = View.GONE
                binding.layoutErrorState.visibility = View.GONE
            }
            is ModerationActionsUiState.Success -> {
                binding.progressBar.visibility = View.GONE
                binding.layoutEmptyState.visibility = View.GONE
                binding.layoutErrorState.visibility = View.GONE
                actionsAdapter.submitList(state.actions)
            }
            is ModerationActionsUiState.Empty -> {
                binding.progressBar.visibility = View.GONE
                binding.layoutEmptyState.visibility = View.VISIBLE
                binding.layoutErrorState.visibility = View.GONE
                binding.tvEmptyTitle.text = "No Audit Log Entries"
                binding.tvEmptyMessage.text = "No moderation actions have been recorded yet."
                actionsAdapter.submitList(emptyList())
            }
            is ModerationActionsUiState.Error -> {
                binding.progressBar.visibility = View.GONE
                binding.layoutEmptyState.visibility = View.GONE
                binding.layoutErrorState.visibility = View.VISIBLE
                if (state.isForbidden) {
                    binding.tvErrorTitle.text = "Access Denied"
                    binding.tvErrorMessage.text = state.message
                    binding.btnErrorAction.visibility = View.GONE
                } else {
                    binding.tvErrorTitle.text = "Unable to Load Audit Log"
                    binding.tvErrorMessage.text = state.message
                    binding.btnErrorAction.visibility = View.VISIBLE
                }
                actionsAdapter.submitList(emptyList())
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
