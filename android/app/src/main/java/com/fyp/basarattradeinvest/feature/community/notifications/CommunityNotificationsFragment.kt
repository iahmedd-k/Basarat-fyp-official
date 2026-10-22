package com.fyp.basarattradeinvest.feature.community.notifications

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
import com.fyp.basarattradeinvest.databinding.FragmentCommunityNotificationsBinding
import com.fyp.basarattradeinvest.feature.community.adapter.CommunityNotificationAdapter
import kotlinx.coroutines.launch

class CommunityNotificationsFragment : Fragment() {

    private var _binding: FragmentCommunityNotificationsBinding? = null
    private val binding get() = _binding!!

    private val viewModel: CommunityNotificationsViewModel by viewModels {
        CommunityNotificationsViewModel.Factory()
    }

    private lateinit var notificationAdapter: CommunityNotificationAdapter

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentCommunityNotificationsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupToolbar()
        setupRecyclerView()
        setupListeners()
        observeUiState()

        viewModel.loadNotifications()
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnMarkAllRead.setOnClickListener {
            viewModel.markAllAsRead()
            Toast.makeText(requireContext(), "All community notifications marked as read", Toast.LENGTH_SHORT).show()
        }
    }

    private fun setupRecyclerView() {
        notificationAdapter = CommunityNotificationAdapter { notification ->
            if (!notification.isRead) {
                viewModel.markAsRead(notification.id)
            }
            if (!notification.actorUsername.isNullOrBlank()) {
                Toast.makeText(requireContext(), "Activity by @${notification.actorUsername}", Toast.LENGTH_SHORT).show()
            }
        }

        binding.rvNotifications.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = notificationAdapter
        }
    }

    private fun setupListeners() {
        binding.swipeRefresh.setOnRefreshListener {
            viewModel.loadNotifications(unreadOnly = binding.chipUnreadFilter.isChecked, isRefresh = true)
        }

        binding.btnRetry.setOnClickListener {
            viewModel.loadNotifications(unreadOnly = binding.chipUnreadFilter.isChecked)
        }

        binding.chipUnreadFilter.setOnCheckedChangeListener { _, isChecked ->
            viewModel.loadNotifications(unreadOnly = isChecked)
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is CommunityNotificationsUiState.Loading -> {
                            binding.progressBar.visibility = View.VISIBLE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                        }
                        is CommunityNotificationsUiState.Success -> {
                            binding.progressBar.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false

                            notificationAdapter.submitList(state.notifications)

                            if (state.unreadCount > 0) {
                                binding.tvUnreadCounterBadge.visibility = View.VISIBLE
                                binding.tvUnreadCounterBadge.text = "${state.unreadCount} Unread"
                            } else {
                                binding.tvUnreadCounterBadge.visibility = View.GONE
                            }
                        }
                        is CommunityNotificationsUiState.Empty -> {
                            binding.progressBar.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false
                            binding.layoutEmpty.visibility = View.VISIBLE
                            binding.layoutError.visibility = View.GONE
                            notificationAdapter.submitList(emptyList())
                        }
                        is CommunityNotificationsUiState.Error -> {
                            binding.progressBar.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
