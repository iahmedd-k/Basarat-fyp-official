package com.fyp.basarattradeinvest.feature.alerts

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentAlertsBinding
import com.fyp.basarattradeinvest.feature.alerts.adapter.AlertHistoryAdapter
import kotlinx.coroutines.launch

/** Alert history only. Rule creation is now a one-tap action from Stock Detail. */
class AlertsFragment : Fragment() {

    private var _binding: FragmentAlertsBinding? = null
    private val binding get() = _binding!!
    private val viewModel: AlertsViewModel by viewModels()
    private lateinit var historyAdapter: AlertHistoryAdapter
    private var renderingFilters = false

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentAlertsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupList()
        setupListeners()
        observeState()
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private fun setupList() {
        historyAdapter = AlertHistoryAdapter { alert ->
            if (!alert.isRead) viewModel.markAlertAsRead(alert.id)
        }
        binding.rvAlertHistory.layoutManager = LinearLayoutManager(requireContext())
        binding.rvAlertHistory.adapter = historyAdapter
    }

    private fun setupListeners() {
        binding.btnBack.setOnClickListener { findNavController().navigateUp() }
        binding.btnHeaderRefresh.setOnClickListener { viewModel.loadData() }
        binding.swipeRefresh.setColorSchemeResources(R.color.color_brand_primary)
        binding.swipeRefresh.setOnRefreshListener { viewModel.loadData(isSwipeRefresh = true) }
        binding.chipGroupHistoryFilter.setOnCheckedStateChangeListener { _, checkedIds ->
            if (!renderingFilters) {
                viewModel.toggleUnreadFilter(checkedIds.contains(R.id.chip_filter_unread))
            }
        }
        binding.btnRetry.setOnClickListener { viewModel.loadData() }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    binding.swipeRefresh.isRefreshing = false
                    when (state) {
                        is AlertsUiState.Loading -> {
                            binding.layoutLoading.visibility = View.VISIBLE
                            binding.chipGroupHistoryFilter.visibility = View.GONE
                            binding.rvAlertHistory.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                        }

                        is AlertsUiState.Success -> {
                            binding.layoutLoading.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.chipGroupHistoryFilter.visibility = View.VISIBLE
                            renderingFilters = true
                            binding.chipFilterAll.isChecked = !state.unreadOnlyFilter
                            binding.chipFilterUnread.isChecked = state.unreadOnlyFilter
                            renderingFilters = false
                            binding.chipFilterUnread.text = if (state.unreadCount > 0) {
                                "Unread (${state.unreadCount})"
                            } else {
                                "Unread"
                            }

                            val filtered = state.filteredAlerts
                            historyAdapter.submitList(filtered)
                            if (filtered.isEmpty()) {
                                binding.rvAlertHistory.visibility = View.GONE
                                binding.layoutEmpty.visibility = View.VISIBLE
                                binding.tvEmptyTitle.text = if (state.unreadOnlyFilter) {
                                    "No unread alerts"
                                } else {
                                    "No alerts yet"
                                }
                                binding.tvEmptyDescription.text = if (state.unreadOnlyFilter) {
                                    "You’re all caught up."
                                } else {
                                    "Price alerts will appear here after the backend triggers them."
                                }
                            } else {
                                binding.rvAlertHistory.visibility = View.VISIBLE
                                binding.layoutEmpty.visibility = View.GONE
                            }

                            state.actionMessage?.let { message ->
                                Toast.makeText(requireContext(), message, Toast.LENGTH_SHORT).show()
                                viewModel.clearActionMessage()
                            }
                        }

                        is AlertsUiState.Empty -> {
                            binding.layoutLoading.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.rvAlertHistory.visibility = View.GONE
                            binding.chipGroupHistoryFilter.visibility = View.VISIBLE
                            binding.layoutEmpty.visibility = View.VISIBLE
                            binding.tvEmptyTitle.text = "No alerts yet"
                            binding.tvEmptyDescription.text = state.message
                        }

                        is AlertsUiState.Error -> {
                            binding.layoutLoading.visibility = View.GONE
                            binding.chipGroupHistoryFilter.visibility = View.GONE
                            binding.rvAlertHistory.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }
}
