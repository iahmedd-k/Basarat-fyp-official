package com.fyp.basarattradeinvest.feature.community.profile

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.CommunityFeedCache
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityPostList
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import com.fyp.basarattradeinvest.domain.usecase.community.GetCommunityFeedUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetMyCommunityProfileUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetMyPostsUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetUserCommunityProfileUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetUserPostsUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.LikeCommunityPostUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.UnlikeCommunityPostUseCase
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CommunityProfileViewModel(
    private val getMyProfileUseCase: GetMyCommunityProfileUseCase,
    private val getUserProfileUseCase: GetUserCommunityProfileUseCase,
    private val getMyPostsUseCase: GetMyPostsUseCase,
    private val getUserPostsUseCase: GetUserPostsUseCase,
    private val getCommunityFeedUseCase: GetCommunityFeedUseCase,
    private val likePostUseCase: LikeCommunityPostUseCase,
    private val unlikePostUseCase: UnlikeCommunityPostUseCase,
    private val appContext: Context? = null
) : ViewModel() {

    private val _uiState = MutableStateFlow<CommunityProfileUiState>(CommunityProfileUiState.Loading)
    val uiState: StateFlow<CommunityProfileUiState> = _uiState.asStateFlow()

    private var currentUserId: String? = null
    private var currentFeedMode: CommunityFeedMode = CommunityFeedMode.COMMUNITY_FEED
    private var currentPostTypeFilter: String? = null
    private var currentStockSymbolFilter: String? = null
    private var postCursor: String? = null
    private var isLoadingMore = false
    // Whose feed the post list on screen belongs to. The header can land before the feed, and the
    // list kept while waiting must be the same account's, never the previously viewed profile's.
    private var displayedPostsUserId: String? = null
    // Measured: limit=8 took 22.6s and limit=20 took 23.4s, so the server cost is fixed and a
    // smaller first page buys nothing. Kept at 20; loadMorePosts() is what exposes posts beyond it.
    private val pageLimit = 20
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L
    private var loadGeneration = 0

    fun ensureLoaded(userId: String? = null, isRefresh: Boolean = false) {
        val state = _uiState.value
        val isSameProfile = currentUserId == userId && state is CommunityProfileUiState.Success
        val shouldLoad = isRefresh || !isSameProfile || System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
        if (shouldLoad) {
            loadProfile(userId = userId, isRefresh = isRefresh)
        }
    }

    fun loadProfile(userId: String? = null, isRefresh: Boolean = false) {
        val previousUserId = currentUserId
        currentUserId = userId
        val generation = ++loadGeneration
        val isSelf = isSelfProfile(userId)

        viewModelScope.launch {
            // /community/feed needs ~23s before it can answer, so paint the last snapshot for this
            // exact profile+filter key first and let the network refresh replace it. Without a
            // snapshot, anything already on screen belongs to another account or filter and is
            // dropped rather than shown under a header it does not belong to.
            val screenBelongsToThisKey = displayedPostsUserId == userId &&
                _uiState.value is CommunityProfileUiState.Success
            if (!screenBelongsToThisKey) {
                if (!seedFromCache() && _uiState.value is CommunityProfileUiState.Success) {
                    postCursor = null
                    _uiState.value = CommunityProfileUiState.Loading
                }
            }

            val currentState = _uiState.value
            val isSameProfile = previousUserId == userId && currentState is CommunityProfileUiState.Success
            if (!isRefresh && isSameProfile && System.currentTimeMillis() - lastSuccessfulFetchAt <= freshnessWindowMs) {
                return@launch
            }
            if (!isRefresh && currentState !is CommunityProfileUiState.Success) {
                _uiState.value = CommunityProfileUiState.Loading
            }

            // Header and feed are independent endpoints; awaiting them one after the other made
            // the user wait for two round trips before anything was drawn.
            coroutineScope {
                val profileDeferred = async {
                    if (isSelf) getMyProfileUseCase() else getUserProfileUseCase(userId!!)
                }
                val postsDeferred = async { fetchPosts(isSelf, userId) }

                val profileResult = profileDeferred.await()
                if (generation != loadGeneration) return@coroutineScope

                val profile = profileResult.getOrNull()
                if (profile == null) {
                    postsDeferred.cancel()
                    val errorMsg = profileResult.exceptionOrNull()?.message ?: "Unable to load community profile"
                    _uiState.value = CommunityProfileUiState.Error(errorMsg)
                    return@coroutineScope
                }

                lastSuccessfulFetchAt = System.currentTimeMillis()
                // Keep the posts already on screen — cached or loaded — while this profile's feed is
                // still in flight, but never another account's.
                val retained = if (displayedPostsUserId == userId) {
                    (currentState as? CommunityProfileUiState.Success)
                } else null
                _uiState.value = CommunityProfileUiState.Success(
                    profile = profile,
                    posts = retained?.posts ?: emptyList(),
                    hasMorePosts = retained?.hasMorePosts ?: false,
                    isRefreshing = false,
                    feedMode = currentFeedMode,
                    isPostsLoading = true
                )

                val postsResult = postsDeferred.await()
                if (generation != loadGeneration) return@coroutineScope
                publishPosts(postsResult)
            }
        }
    }

    fun setFeedMode(mode: CommunityFeedMode) {
        if (currentFeedMode == mode && _uiState.value is CommunityProfileUiState.Success) {
            return
        }
        currentFeedMode = mode
        reloadPosts()
    }

    fun setCommunityFilter(postType: String? = null, stockSymbol: String? = null) {
        val nextPostType = postType?.takeIf { it.isNotBlank() && it != "ALL" }
        val nextStockSymbol = stockSymbol?.trim()?.takeIf { it.isNotBlank() }
        val unchanged = nextPostType == currentPostTypeFilter && nextStockSymbol == currentStockSymbolFilter
        currentPostTypeFilter = nextPostType
        currentStockSymbolFilter = nextStockSymbol
        if (unchanged && _uiState.value is CommunityProfileUiState.Success) return
        reloadPosts()
    }

    fun clearCommunityFilter() {
        currentPostTypeFilter = null
        currentStockSymbolFilter = null
        reloadPosts()
    }

    /** Feed filters only change the post list, so the header is not re-requested. */
    private fun reloadPosts() {
        val userId = currentUserId
        val currentState = _uiState.value
        if (currentState !is CommunityProfileUiState.Success) {
            loadProfile(userId = userId, isRefresh = true)
            return
        }

        val generation = ++loadGeneration
        val isSelf = isSelfProfile(userId)
        // The previous key's posts must not stay on screen while a different filter loads; swap in
        // this key's cached page if there is one, otherwise clear them.
        postCursor = null
        val seeded = readCacheSnapshot()
        _uiState.value = currentState.copy(
            posts = seeded?.posts ?: emptyList(),
            hasMorePosts = seeded?.hasMore ?: false,
            isPostsLoading = true,
            feedMode = currentFeedMode
        )
        postCursor = seeded?.cursor
        displayedPostsUserId = userId

        viewModelScope.launch {
            val postsResult = fetchPosts(isSelf, userId)
            if (generation != loadGeneration) return@launch
            publishPosts(postsResult)
        }
    }

    private suspend fun fetchPosts(
        isSelf: Boolean,
        userId: String?,
        cursor: String? = null
    ): Result<CommunityPostList> {
        return if (isSelf) {
            if (currentFeedMode == CommunityFeedMode.COMMUNITY_FEED) {
                getCommunityFeedUseCase(
                    stockSymbol = currentStockSymbolFilter,
                    postType = currentPostTypeFilter,
                    mine = false,
                    cursor = cursor,
                    limit = pageLimit
                )
            } else {
                getMyPostsUseCase(cursor = cursor, limit = pageLimit)
            }
        } else {
            getUserPostsUseCase(userId = userId!!, cursor = cursor, limit = pageLimit)
        }
    }

    /** Streams the next page in as the user nears the bottom instead of capping the feed at one page. */
    fun loadMorePosts() {
        val state = _uiState.value as? CommunityProfileUiState.Success ?: return
        val cursor = postCursor
        val userId = currentUserId
        if (cursor == null || !state.hasMorePosts || isLoadingMore || state.isPostsLoading) return
        val isSelf = isSelfProfile(userId)
        if (!isSelf && userId.isNullOrBlank()) return

        isLoadingMore = true
        val generation = loadGeneration
        viewModelScope.launch {
            val page = fetchPosts(isSelf, userId, cursor).getOrNull()
            if (generation == loadGeneration) appendPosts(page)
            isLoadingMore = false
        }
    }

    private fun appendPosts(page: CommunityPostList?) {
        if (page == null) return
        val currentState = _uiState.value as? CommunityProfileUiState.Success ?: return
        postCursor = page.cursor ?: postCursor
        displayedPostsUserId = currentUserId
        _uiState.value = currentState.copy(
            posts = dedupePosts(currentState.posts + page.posts),
            hasMorePosts = page.hasMore
        )
        writeCache()
    }

    private fun dedupePosts(posts: List<CommunityPost>): List<CommunityPost> =
        posts.distinctBy { it.id }.distinctBy { "${it.authorDisplayName}_${it.content.trim()}" }

    private fun readCacheSnapshot(): CommunityFeedCache.Snapshot? {
        val context = appContext ?: return null
        val key = CommunityFeedCache.keyFor(
            userId = currentUserId,
            feedMode = currentFeedMode.name,
            postType = currentPostTypeFilter,
            stockSymbol = currentStockSymbolFilter
        )
        return CommunityFeedCache.read(context, key)
    }

    /** Installs the last snapshot for the current profile+filter key; false when there is none. */
    private fun seedFromCache(): Boolean {
        val snapshot = readCacheSnapshot() ?: return false
        postCursor = snapshot.cursor
        displayedPostsUserId = currentUserId
        _uiState.value = CommunityProfileUiState.Success(
            profile = snapshot.profile,
            posts = snapshot.posts,
            hasMorePosts = snapshot.hasMore,
            feedMode = currentFeedMode,
            isPostsLoading = true
        )
        return true
    }

    private fun writeCache() {
        if (appContext == null) return
        val state = _uiState.value as? CommunityProfileUiState.Success ?: return
        if (state.posts.isEmpty()) return
        val key = CommunityFeedCache.keyFor(
            userId = currentUserId,
            feedMode = currentFeedMode.name,
            postType = currentPostTypeFilter,
            stockSymbol = currentStockSymbolFilter
        )
        CommunityFeedCache.write(
            appContext,
            key,
            CommunityFeedCache.Snapshot(
                profile = state.profile,
                posts = state.posts,
                cursor = postCursor,
                hasMore = state.hasMorePosts,
                savedAt = System.currentTimeMillis()
            )
        )
    }

    private fun publishPosts(postsResult: Result<CommunityPostList>) {
        val currentState = _uiState.value as? CommunityProfileUiState.Success ?: return
        val payload = postsResult.getOrNull()
        if (payload == null) {
            // A failed refresh keeps what is already on screen instead of replacing it with nothing.
            _uiState.value = currentState.copy(isPostsLoading = false, feedMode = currentFeedMode)
            return
        }
        val posts = dedupePosts(payload.posts)
        postCursor = payload.cursor
        displayedPostsUserId = currentUserId

        _uiState.value = currentState.copy(
            posts = posts,
            hasMorePosts = payload.hasMore,
            isRefreshing = false,
            isPostsLoading = false,
            feedMode = currentFeedMode
        )
        writeCache()
    }

    private fun isSelfProfile(userId: String?): Boolean =
        userId.isNullOrBlank() || userId.equals("me", ignoreCase = true)

    fun toggleLike(post: CommunityPost) {
        val currentState = _uiState.value as? CommunityProfileUiState.Success ?: return

        val newLiked = !post.likedByMe
        val newLikeCount = if (newLiked) post.likeCount + 1 else maxOf(0, post.likeCount - 1)

        val updatedPosts = currentState.posts.map { item ->
            if (item.id == post.id) {
                item.copy(likedByMe = newLiked, likeCount = newLikeCount)
            } else {
                item
            }
        }

        // Optimistic UI update
        _uiState.value = currentState.copy(posts = updatedPosts)

        viewModelScope.launch {
            if (newLiked) {
                likePostUseCase(post.id)
            } else {
                unlikePostUseCase(post.id)
            }
        }
    }

    fun updateCommentCount(postId: String, newCount: Int) {
        val currentState = _uiState.value as? CommunityProfileUiState.Success ?: return

        val updatedPosts = currentState.posts.map { item ->
            if (item.id == postId) {
                item.copy(commentCount = newCount)
            } else {
                item
            }
        }

        _uiState.value = currentState.copy(posts = updatedPosts)
    }

    class Factory(
        private val repository: CommunityRepository = CommunityRepositoryImpl(),
        private val appContext: Context? = null
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(CommunityProfileViewModel::class.java)) {
                return CommunityProfileViewModel(
                    getMyProfileUseCase = GetMyCommunityProfileUseCase(repository),
                    getUserProfileUseCase = GetUserCommunityProfileUseCase(repository),
                    getMyPostsUseCase = GetMyPostsUseCase(repository),
                    getUserPostsUseCase = GetUserPostsUseCase(repository),
                    getCommunityFeedUseCase = GetCommunityFeedUseCase(repository),
                    likePostUseCase = LikeCommunityPostUseCase(repository),
                    unlikePostUseCase = UnlikeCommunityPostUseCase(repository),
                    appContext = appContext
                ) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class")
        }
    }
}
