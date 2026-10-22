package com.fyp.basarattradeinvest.feature.community.profile

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.navigation.fragment.findNavController
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.fyp.basarattradeinvest.R
import com.fyp.basarattradeinvest.databinding.FragmentCommunityProfileBinding
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.fyp.basarattradeinvest.feature.community.adapter.CommunityPostAdapter
import com.fyp.basarattradeinvest.feature.community.comments.CommunityCommentsBottomSheetDialogFragment
import kotlinx.coroutines.launch

class CommunityProfileFragment : Fragment() {

    private var _binding: FragmentCommunityProfileBinding? = null
    private val binding get() = _binding!!

    private val viewModel: CommunityProfileViewModel by activityViewModels {
        CommunityProfileViewModel.Factory(appContext = requireContext().applicationContext)
    }

    private lateinit var postAdapter: CommunityPostAdapter
    private var targetUserId: String? = null
    private var lastBoundHeader: Pair<CommunityProfile, CommunityFeedMode>? = null
    private var lastBoundPosts: List<CommunityPost>? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        targetUserId = arguments?.getString("user_id")
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentCommunityProfileBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        setupToolbar()
        setupRecyclerView()
        setupListeners()
        observeUiState()

        viewModel.ensureLoaded(userId = targetUserId)
    }

    private fun setupToolbar() {
        binding.toolbar.setNavigationOnClickListener {
            findNavController().navigateUp()
        }

        binding.btnNotifications.setOnClickListener {
            findNavController().navigate(R.id.communityNotificationsFragment)
        }
    }

    private fun setupRecyclerView() {
        postAdapter = CommunityPostAdapter(
            onPostClick = { post ->
                if (!post.stockSymbol.isNullOrBlank()) {
                    val bundle = Bundle().apply { putString("symbol", post.stockSymbol) }
                    findNavController().navigate(R.id.stockDetailFragment, bundle)
                } else {
                    Toast.makeText(requireContext(), "Community Post #${post.id.take(6)}", Toast.LENGTH_SHORT).show()
                }
            },
            onLikeClick = { post ->
                viewModel.toggleLike(post)
            },
            onCommentClick = { post ->
                showCommentsBottomSheet(post)
            }
        )

        binding.rvPosts.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = postAdapter
            addOnScrollListener(object : RecyclerView.OnScrollListener() {
                override fun onScrolled(recyclerView: RecyclerView, dx: Int, dy: Int) {
                    if (dy <= 0) return
                    val layoutManager = recyclerView.layoutManager as? LinearLayoutManager ?: return
                    val lastVisible = layoutManager.findLastVisibleItemPosition()
                    if (layoutManager.itemCount > 0 && lastVisible >= layoutManager.itemCount - 3) {
                        viewModel.loadMorePosts()
                    }
                }
            })
        }
    }

    private fun showCommentsBottomSheet(post: CommunityPost) {
        val bottomSheet = CommunityCommentsBottomSheetDialogFragment.newInstance(post.id)
        bottomSheet.onCommentAdded = { newCount ->
            viewModel.updateCommentCount(post.id, newCount)
        }
        bottomSheet.show(childFragmentManager, CommunityCommentsBottomSheetDialogFragment.TAG)
    }

    private fun setupListeners() {
        binding.swipeRefresh.setOnRefreshListener {
            viewModel.loadProfile(userId = targetUserId, isRefresh = true)
        }

        binding.btnRetry.setOnClickListener {
            viewModel.loadProfile(userId = targetUserId)
        }

        binding.btnFollowersStat.setOnClickListener {
            val uid = targetUserId ?: "me"
            val bundle = Bundle().apply {
                putString("user_id", uid)
                putBoolean("is_following", false)
            }
            findNavController().navigate(R.id.communityFollowersFragment, bundle)
        }

        binding.btnFollowingStat.setOnClickListener {
            val uid = targetUserId ?: "me"
            val bundle = Bundle().apply {
                putString("user_id", uid)
                putBoolean("is_following", true)
            }
            findNavController().navigate(R.id.communityFollowersFragment, bundle)
        }

        binding.tabAllFeed.setOnClickListener {
            viewModel.setFeedMode(CommunityFeedMode.COMMUNITY_FEED)
        }

        binding.tabMyPosts.setOnClickListener {
            viewModel.setFeedMode(CommunityFeedMode.MY_POSTS)
        }

        binding.chipFilterAll.setOnClickListener {
            viewModel.setCommunityFilter(postType = null, stockSymbol = null)
            binding.chipFilterAll.isChecked = true
            binding.chipFilterStock.isChecked = false
            binding.chipFilterGeneral.isChecked = false
        }

        binding.chipFilterStock.setOnClickListener {
            viewModel.setCommunityFilter(postType = "STOCK", stockSymbol = null)
            binding.chipFilterAll.isChecked = false
            binding.chipFilterStock.isChecked = true
            binding.chipFilterGeneral.isChecked = false
        }

        binding.chipFilterGeneral.setOnClickListener {
            viewModel.setCommunityFilter(postType = "GENERAL_MARKET", stockSymbol = null)
            binding.chipFilterAll.isChecked = false
            binding.chipFilterStock.isChecked = false
            binding.chipFilterGeneral.isChecked = true
        }

        binding.fabCreatePost.setOnClickListener {
            showCreatePostDialog()
        }

        binding.btnCreateFirstPost.setOnClickListener {
            showCreatePostDialog()
        }
    }

    private fun showCreatePostDialog() {
        val dialog = com.fyp.basarattradeinvest.feature.community.create.CreatePostBottomSheetDialogFragment.newInstance()
        dialog.onPostCreated = {
            viewModel.loadProfile(userId = targetUserId, isRefresh = true)
        }
        dialog.show(childFragmentManager, com.fyp.basarattradeinvest.feature.community.create.CreatePostBottomSheetDialogFragment.TAG)
    }

    private fun observeUiState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.uiState.collect { state ->
                    when (state) {
                        is CommunityProfileUiState.Loading -> {
                            lastBoundHeader = null
                            lastBoundPosts = null
                            binding.layoutProfileSkeleton.visibility = View.VISIBLE
                            binding.layoutPostsSkeleton.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                        }
                        is CommunityProfileUiState.Success -> {
                            binding.layoutProfileSkeleton.visibility = View.GONE
                            binding.layoutError.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false
                            // The header arrives before the feed, so only the post area waits.
                            // Retained posts stay on screen during a refresh, so the skeleton is
                            // for the first page only.
                            binding.layoutPostsSkeleton.visibility =
                                if (state.isPostsLoading && state.posts.isEmpty()) View.VISIBLE else View.GONE

                            val header = state.profile to state.feedMode
                            if (lastBoundHeader != header) {
                                bindProfile(state.profile)
                                bindFeedModeTabs(state.feedMode, state.profile.isOwnProfile)
                                lastBoundHeader = header
                            }

                            if (lastBoundPosts != state.posts) {
                                postAdapter.submitList(state.posts)
                                lastBoundPosts = state.posts
                            }

                            binding.layoutEmptyPosts.visibility =
                                if (!state.isPostsLoading && state.posts.isEmpty()) View.VISIBLE else View.GONE
                        }
                        is CommunityProfileUiState.Error -> {
                            lastBoundHeader = null
                            lastBoundPosts = null
                            binding.layoutProfileSkeleton.visibility = View.GONE
                            binding.layoutPostsSkeleton.visibility = View.GONE
                            binding.swipeRefresh.isRefreshing = false
                            binding.layoutError.visibility = View.VISIBLE
                            binding.tvErrorMessage.text = state.message
                        }
                    }
                }
            }
        }
    }

    private fun bindFeedModeTabs(mode: CommunityFeedMode, isOwnProfile: Boolean) {
        if (!isOwnProfile && targetUserId != null) {
            binding.layoutFeedTabs.visibility = View.GONE
            binding.tvSectionPosts.text = "Posts by ${binding.tvProfileFullName.text}"
            return
        }

        binding.layoutFeedTabs.visibility = View.VISIBLE
        val context = requireContext()

        if (mode == CommunityFeedMode.COMMUNITY_FEED) {
            binding.tabAllFeed.setBackgroundResource(R.drawable.bg_segmented_tab_active)
            binding.tabAllFeed.setTextColor(ContextCompat.getColor(context, R.color.color_text_primary))

            binding.tabMyPosts.setBackgroundColor(android.graphics.Color.TRANSPARENT)
            binding.tabMyPosts.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))

            binding.tvSectionPosts.text = "Community Feed"
        } else {
            binding.tabMyPosts.setBackgroundResource(R.drawable.bg_segmented_tab_active)
            binding.tabMyPosts.setTextColor(ContextCompat.getColor(context, R.color.color_text_primary))

            binding.tabAllFeed.setBackgroundColor(android.graphics.Color.TRANSPARENT)
            binding.tabAllFeed.setTextColor(ContextCompat.getColor(context, R.color.color_text_secondary))

            binding.tvSectionPosts.text = "My Published Posts"
        }
    }

    private fun bindProfile(profile: CommunityProfile) {
        binding.tvToolbarTitle.text = if (profile.isOwnProfile) "Community Hub" else "@${profile.username}"
        binding.tvProfileFullName.text = profile.displayName
        binding.tvProfileUsername.text = "@${profile.username}"

        binding.tvStatsPostsCount.text = profile.publishedPostCount.toString()
        binding.tvStatsFollowersCount.text = profile.followersCount.toString()
        binding.tvStatsFollowingCount.text = profile.followingCount.toString()

        if (!profile.isOwnProfile && profile.isFollowing) {
            binding.tvFollowStatusBadge.visibility = View.VISIBLE
            binding.tvFollowStatusBadge.text = "Following"
        } else {
            binding.tvFollowStatusBadge.visibility = View.GONE
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        lastBoundHeader = null
        lastBoundPosts = null
        _binding = null
    }
}
