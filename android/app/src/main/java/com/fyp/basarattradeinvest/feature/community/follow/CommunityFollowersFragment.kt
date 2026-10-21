package com.fyp.basarattradeinvest.feature.community.follow

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
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentCommunityFollowListBinding
import com.fyp.basarattradeinvest.feature.community.adapter.CommunityUserAdapter
import kotlinx.coroutines.launch

class CommunityFollowersFragment : Fragment() {

    private var _binding: FragmentCommunityFollowListBinding? = null
    private val binding get() = _binding!!

    private val viewModel: CommunityFollowViewModel by viewModels {
        CommunityFollowViewModel.Factory()
    }

    private lateinit var userAdapter: CommunityUserAdapter
    private var userId: String = "me"
    private var isFollowingMode: Boolean = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        userId = arguments?.getString("user_id") ?: "me"
        isFollowingMode = arguments?.getBoolean("is_following") ?: false
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentCommunityFollowListBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupToolbar()
        setupRecyclerView()
        setupListeners()
        observeUiState()

        viewModel.loadUsers(userId = userId, isFollowing = isFollowingMode)
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            findNavController().navigateUp()
        }
        binding.tvToolbarTitle.text = if (isFollowingMode) "Following" else "Followers"
    }

    private fun setupRecyclerView() {
        userAdapter = CommunityUserAdapter { user ->
            val bundle = Bundle().apply { putString("user_id", user.id) }
            findNavController().navigate(R.id.communityProfileFragment, bundle)
        }

        binding.rvUsers.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = userAdapter
        }
    }

    private fun setupListeners() {
        binding.swipeRefresh.setOnRefreshListener {
            viewModel.loadUsers(userId = userId, isFollowing = isFollowingMode, isRefresh = true)
        }

        binding.btnRetry.setOnClickListener {
            viewModel.loadUsers(userId = userId, isFollowing = isFollowingMode)
        }
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is CommunityFollowUiState.Loading -> {
                            binding.progressBar.visibility = View.VISIBLE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                        }
                        is CommunityFollowUiState.Success -> {
                            binding.progressBar.visibility = View.GONE
                            binding.layoutEmpty.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false
                            userAdapter.submitList(state.users)
                        }
                        is CommunityFollowUiState.Empty -> {
                            binding.progressBar.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false
                            binding.layoutEmpty.visibility = View.VISIBLE
                            binding.layoutError.visibility = View.GONE
                            userAdapter.submitList(emptyList())
                            binding.tvEmptyMessage.text = if (isFollowingMode) {
                                "Not following any traders yet"
                            } else {
                                "No followers yet"
                            }
                        }
                        is CommunityFollowUiState.Error -> {
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
