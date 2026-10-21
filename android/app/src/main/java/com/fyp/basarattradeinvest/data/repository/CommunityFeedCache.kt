package com.fyp.basarattradeinvest.data.repository

import android.content.Context
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.google.gson.Gson

/**
 * Last-seen community profile and feed. /community/feed answers in roughly 22 seconds, so painting
 * what was on screen last time while the refresh runs in the background is the only client-side win.
 */
object CommunityFeedCache {

    private const val PREFS_NAME = "basarat_community_feed_cache"
    private const val MAX_AGE_MS = 24 * 60 * 60 * 1000L

    data class Snapshot(
        val profile: CommunityProfile,
        val posts: List<CommunityPost>,
        val cursor: String?,
        val hasMore: Boolean,
        val savedAt: Long
    )

    private val gson = Gson()

    /** Scoped to the requested account so a cached profile can never surface for another user. */
    fun keyFor(
        userId: String?,
        feedMode: String,
        postType: String?,
        stockSymbol: String?
    ): String = listOf(
        userId ?: "self",
        feedMode,
        postType ?: "-",
        stockSymbol ?: "-"
    ).joinToString("|")

    fun read(context: Context, key: String): Snapshot? {
        val json = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(key, null) ?: return null
        val snapshot = runCatching { gson.fromJson(json, Snapshot::class.java) }.getOrNull() ?: return null
        if (snapshot.posts.isEmpty()) return null
        if (System.currentTimeMillis() - snapshot.savedAt > MAX_AGE_MS) return null
        return snapshot
    }

    fun write(context: Context, key: String, snapshot: Snapshot) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit()
            .putString(key, gson.toJson(snapshot))
            .apply()
    }
}
