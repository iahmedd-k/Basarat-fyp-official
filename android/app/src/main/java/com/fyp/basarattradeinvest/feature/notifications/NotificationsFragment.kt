package com.fyp.basarattradeinvest.feature.notifications

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.core.notifications.NotificationBadgeState
import com.fyp.basarattradeinvest.databinding.FragmentNotificationsBinding
import com.fyp.basarattradeinvest.feature.notifications.adapter.NotificationsAdapter
import kotlinx.coroutines.launch

class NotificationsFragment : Fragment() {

    private var _binding: FragmentNotificationsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: NotificationsViewModel by viewModels()
    private lateinit var adapter: NotificationsAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentNotificationsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupRecyclerView()
        setupListeners()
        observeData()
        viewLifecycleOwner.lifecycleScope.launch { NotificationBadgeState.refresh() }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private fun setupRecyclerView() {
        adapter = NotificationsAdapter(
            onItemClick = { item ->
                if (!item.isRead) {
                    viewModel.markAsRead(item.id)
                }
            }
        )

        val layoutManager = LinearLayoutManager(requireContext())
        binding.rvNotifications.apply {
            this.layoutManager = layoutManager
            this.adapter = this@NotificationsFragment.adapter

            // Pagination Scroll Listener
            addOnScrollListener(object : RecyclerView.OnScrollListener() {
                override fun onScrolled(recyclerView: RecyclerView, dx: Int, dy: Int) {
                    super.onScrolled(recyclerView, dx, dy)
                    if (dy > 0) {
                        val visibleItemCount = layoutManager.childCount
                        val totalItemCount = layoutManager.itemCount
                        val firstVisibleItemPosition = layoutManager.findFirstVisibleItemPosition()

                        if ((visibleItemCount + firstVisibleItemPosition) >= totalItemCount - 4 &&
                            firstVisibleItemPosition >= 0
                        ) {
                            viewModel.loadNextPage()
                        }
                    }
                }
            })
        }
    }

    private fun setupListeners() {
        binding.btnBack.setOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnRefresh.setOnClickListener {
            viewModel.refresh()
        }

        binding.swipeRefresh.setColorSchemeResources(R.color.color_brand_primary)
        binding.swipeRefresh.setOnRefreshListener {
            viewModel.refresh()
        }

        binding.chipGroupFilters.setOnCheckedStateChangeListener { _, checkedIds ->
            val unreadOnly = checkedIds.contains(R.id.chip_unread)
            viewModel.toggleUnreadFilter(unreadOnly)
        }

        binding.btnRetry.setOnClickListener {
            viewModel.loadInitialNotifications()
        }
    }

    private fun observeData() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    binding.swipeRefresh.isRefreshing = false

                    when (state) {
                        is NotificationsUiState.Loading -> {
                            binding.layoutLoading.visibility = View.VISIBLE
                            binding.rvNotifications.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.progressPagination.visibility = View.GONE
                        }

                        is NotificationsUiState.Success -> {
                            binding.layoutLoading.visibility = View.GONE
                            binding.rvNotifications.visibility = View.VISIBLE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE

                            adapter.submitList(state.items)

                            binding.progressPagination.visibility =
                                if (state.isPaginating) View.VISIBLE else View.GONE

                            val unreadCount = state.unreadCount
                            binding.tvTitle.text = if (unreadCount > 0) {
                                "Notifications ($unreadCount)"
                            } else {
                                "Notifications"
                            }
                        }

                        is NotificationsUiState.Empty -> {
                            binding.layoutLoading.visibility = View.GONE
                            binding.rvNotifications.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.VISIBLE
                            binding.progressPagination.visibility = View.GONE

                            if (state.unreadOnlyFilter) {
                                binding.tvEmptyTitle.text = "No Unread Notifications"
                                binding.tvEmptyDescription.text = "You've read all your notifications. Switch to 'All' to view your notification history."
                            } else {
                                binding.tvEmptyTitle.text = "No Notifications Yet"
                                binding.tvEmptyDescription.text = "You're all caught up! New price alerts, market updates, and portfolio notices will appear here."
                            }
                        }

                        is NotificationsUiState.Error -> {
                            binding.layoutLoading.visibility = View.GONE
                            binding.rvNotifications.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.VISIBLE
                            binding.progressPagination.visibility = View.GONE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }
}
