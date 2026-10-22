package com.fyp.basarattradeinvest.domain.model.ipo

import com.fyp.basarattradeinvest.data.remote.dto.ipo.IpoCalendarEventDto
import com.fyp.basarattradeinvest.data.remote.dto.ipo.IpoItemDto
import com.fyp.basarattradeinvest.data.remote.dto.ipo.IpoPerformanceItemDto
import com.fyp.basarattradeinvest.data.remote.dto.ipo.IpoPerformanceResponseDto

data class IpoItem(
    val id: String?,
    val symbol: String,
    val companyName: String,
    val sector: String?,
    val status: String?,
    val issueSizeShares: Long?,
    val issueSizePkr: Double?,
    val floorPrice: Double?,
    val strikePrice: Double?,
    val listingPrice: Double?,
    val currentPrice: Double?,
    val bookBuildingStart: String?,
    val bookBuildingEnd: String?,
    val publicSubscriptionStart: String?,
    val publicSubscriptionEnd: String?,
    val listingDate: String?,
    val leadManager: String?,
    val isShariahCompliant: Boolean,
    val prospectusUrl: String?,
    val description: String?,
    val subscriptionMultiplier: Double?,
    val listingGainPct: Double?,
    val currentGainPct: Double?,
    val createdAt: String?,
    val updatedAt: String?
)

fun IpoItemDto.toDomain(): IpoItem = IpoItem(
    id = id,
    symbol = symbol ?: "",
    companyName = companyName ?: symbol ?: "",
    sector = sector,
    status = status,
    issueSizeShares = issueSizeShares,
    issueSizePkr = issueSizePkr,
    floorPrice = floorPrice,
    strikePrice = strikePrice,
    listingPrice = listingPrice,
    currentPrice = currentPrice,
    bookBuildingStart = bookBuildingStart,
    bookBuildingEnd = bookBuildingEnd,
    publicSubscriptionStart = publicSubscriptionStart,
    publicSubscriptionEnd = publicSubscriptionEnd,
    listingDate = listingDate,
    leadManager = leadManager,
    isShariahCompliant = isShariahCompliant ?: false,
    prospectusUrl = prospectusUrl,
    description = description,
    subscriptionMultiplier = subscriptionMultiplier,
    listingGainPct = listingGainPct,
    currentGainPct = currentGainPct,
    createdAt = createdAt,
    updatedAt = updatedAt
)

data class IpoCalendarEvent(
    val ipoId: String?,
    val symbol: String,
    val companyName: String,
    val eventType: String,
    val eventDate: String?,
    val status: String?,
    val priceInfo: String?
)

fun IpoCalendarEventDto.toDomain(): IpoCalendarEvent = IpoCalendarEvent(
    ipoId = ipoId,
    symbol = symbol ?: "",
    companyName = companyName ?: symbol ?: "",
    eventType = eventType ?: "",
    eventDate = eventDate,
    status = status,
    priceInfo = priceInfo
)

data class IpoPerformanceItem(
    val symbol: String,
    val companyName: String,
    val sector: String?,
    val listingDate: String?,
    val offerPrice: Double?,
    val firstDayClose: Double?,
    val currentPrice: Double?,
    val firstDayReturnPct: Double?,
    val totalReturnPct: Double?
)

fun IpoPerformanceItemDto.toDomain(): IpoPerformanceItem = IpoPerformanceItem(
    symbol = symbol ?: "",
    companyName = companyName ?: symbol ?: "",
    sector = sector,
    listingDate = listingDate,
    offerPrice = offerPrice,
    firstDayClose = firstDayClose,
    currentPrice = currentPrice,
    firstDayReturnPct = firstDayReturnPct,
    totalReturnPct = totalReturnPct
)

data class IpoPerformanceSummary(
    val totalListed: Int,
    val averageListingDayGainPct: Double?,
    val topPerformers: List<IpoPerformanceItem>,
    val recentListings: List<IpoPerformanceItem>
)

fun IpoPerformanceResponseDto.toDomain(): IpoPerformanceSummary = IpoPerformanceSummary(
    totalListed = totalListed ?: 0,
    averageListingDayGainPct = averageListingDayGainPct,
    topPerformers = topPerformers?.map { it.toDomain() } ?: emptyList(),
    recentListings = recentListings?.map { it.toDomain() } ?: emptyList()
)
