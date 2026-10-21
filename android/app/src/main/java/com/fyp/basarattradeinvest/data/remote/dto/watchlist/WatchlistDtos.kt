package com.fyp.basarattradeinvest.data.remote.dto.watchlist

import com.google.gson.annotations.SerializedName

data class WatchlistDetailResponseDto(
    @SerializedName("id") val id: String,
    @SerializedName("user_id") val userId: String,
    @SerializedName("name") val name: String,
    @SerializedName("description") val description: String? = null,
    @SerializedName("is_default") val isDefault: Boolean = false,
    @SerializedName("items") val items: List<WatchlistItemResponseDto> = emptyList(),
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class WatchlistItemResponseDto(
    @SerializedName("id") val id: String,
    @SerializedName("watchlist_id") val watchlistId: String,
    @SerializedName("symbol") val symbol: String,
    @SerializedName("name") val name: String? = null,
    @SerializedName("sector") val sector: String? = null,
    @SerializedName("target_price") val targetPrice: Double? = null,
    @SerializedName("notes") val notes: String? = null,
    @SerializedName("current_price") val currentPrice: Double? = null,
    @SerializedName("change") val change: Double? = null,
    @SerializedName("change_pct") val changePct: Double? = null,
    @SerializedName("high") val high: Double? = null,
    @SerializedName("low") val low: Double? = null,
    @SerializedName("volume") val volume: Long? = null,
    @SerializedName("is_stale") val isStale: Boolean = false,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class WatchlistItemCreateRequestDto(
    @SerializedName("symbol") val symbol: String,
    @SerializedName("target_price") val targetPrice: Double? = null,
    @SerializedName("notes") val notes: String? = null
)

data class WatchlistCheckResponseDto(
    @SerializedName("symbol") val symbol: String,
    @SerializedName("is_in_watchlist") val isInWatchlist: Boolean,
    @SerializedName("watchlist_ids") val watchlistIds: List<String> = emptyList()
)
