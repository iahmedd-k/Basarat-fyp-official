package com.fyp.basarattradeinvest.data.remote.dto.ipo

import com.google.gson.annotations.SerializedName

data class IpoItemDto(
    @SerializedName("id") val id: String?,
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("company_name") val companyName: String?,
    @SerializedName("sector") val sector: String?,
    @SerializedName("status") val status: String?,
    @SerializedName("issue_size_shares") val issueSizeShares: Long?,
    @SerializedName("issue_size_pkr") val issueSizePkr: Double?,
    @SerializedName("floor_price") val floorPrice: Double?,
    @SerializedName("strike_price") val strikePrice: Double?,
    @SerializedName("listing_price") val listingPrice: Double?,
    @SerializedName("current_price") val currentPrice: Double?,
    @SerializedName("book_building_start") val bookBuildingStart: String?,
    @SerializedName("book_building_end") val bookBuildingEnd: String?,
    @SerializedName("public_subscription_start") val publicSubscriptionStart: String?,
    @SerializedName("public_subscription_end") val publicSubscriptionEnd: String?,
    @SerializedName("listing_date") val listingDate: String?,
    @SerializedName("lead_manager") val leadManager: String?,
    @SerializedName("is_shariah_compliant") val isShariahCompliant: Boolean?,
    @SerializedName("prospectus_url") val prospectusUrl: String?,
    @SerializedName("description") val description: String?,
    @SerializedName("subscription_multiplier") val subscriptionMultiplier: Double?,
    @SerializedName("listing_gain_pct") val listingGainPct: Double?,
    @SerializedName("current_gain_pct") val currentGainPct: Double?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("updated_at") val updatedAt: String?
)

data class IposResponseDto(
    @SerializedName("total") val total: Int?,
    @SerializedName("upcoming_count") val upcomingCount: Int?,
    @SerializedName("active_count") val activeCount: Int?,
    @SerializedName("listed_count") val listedCount: Int?,
    @SerializedName("ipos") val ipos: List<IpoItemDto>?
)

data class IpoCalendarEventDto(
    @SerializedName("ipo_id") val ipoId: String?,
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("company_name") val companyName: String?,
    @SerializedName("event_type") val eventType: String?,
    @SerializedName("event_date") val eventDate: String?,
    @SerializedName("status") val status: String?,
    @SerializedName("price_info") val priceInfo: String?
)

data class IpoCalendarResponseDto(
    @SerializedName("total_events") val totalEvents: Int?,
    @SerializedName("upcoming_milestones") val upcomingMilestones: List<IpoCalendarEventDto>?
)

data class IpoPerformanceItemDto(
    @SerializedName("symbol") val symbol: String?,
    @SerializedName("company_name") val companyName: String?,
    @SerializedName("sector") val sector: String?,
    @SerializedName("listing_date") val listingDate: String?,
    @SerializedName("offer_price") val offerPrice: Double?,
    @SerializedName("first_day_close") val firstDayClose: Double?,
    @SerializedName("current_price") val currentPrice: Double?,
    @SerializedName("first_day_return_pct") val firstDayReturnPct: Double?,
    @SerializedName("total_return_pct") val totalReturnPct: Double?
)

data class IpoPerformanceResponseDto(
    @SerializedName("total_listed") val totalListed: Int?,
    @SerializedName("average_listing_day_gain_pct") val averageListingDayGainPct: Double?,
    @SerializedName("top_performers") val topPerformers: List<IpoPerformanceItemDto>?,
    @SerializedName("recent_listings") val recentListings: List<IpoPerformanceItemDto>?
)
