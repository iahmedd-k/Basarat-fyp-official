package com.fyp.basarattradeinvest.data.remote.dto.user

/**
 * UserPayloads
 *
 * Centralized registry of pre-constructed payloads and factories for all BASARAT backend
 * User, Risk Profile, and Notification Preferences endpoints.
 */
object UserPayloads {

    // 1. PROFILE UPDATE / SET PAYLOADS (POST / PATCH /api/v1/users/me)
    fun updateProfilePayload(
        fullName: String? = "Basarat Trader",
        avatarUrl: String? = null,
        riskTolerance: String? = "moderate",
        sectorPreferences: List<String>? = listOf("Commercial Banks", "Technology"),
        investmentHorizon: String? = "medium_term"
    ) = UpdateProfileRequestDto(
        fullName = fullName,
        avatarUrl = avatarUrl,
        riskTolerance = riskTolerance,
        sectorPreferences = sectorPreferences,
        investmentHorizon = investmentHorizon
    )

    val DEFAULT_PROFILE_UPDATE = UpdateProfileRequestDto(
        fullName = "Basarat Pro Trader",
        avatarUrl = null,
        riskTolerance = "moderate",
        sectorPreferences = listOf("Commercial Banks", "Technology", "Oil & Gas"),
        investmentHorizon = "medium_term"
    )

    val CONSERVATIVE_RISK_PROFILE = UpdateProfileRequestDto(
        riskTolerance = "conservative",
        investmentHorizon = "long_term",
        sectorPreferences = listOf("Commercial Banks", "Fertilizer")
    )

    val AGGRESSIVE_RISK_PROFILE = UpdateProfileRequestDto(
        riskTolerance = "aggressive",
        investmentHorizon = "short_term",
        sectorPreferences = listOf("Technology", "Cement")
    )

    // 2. NOTIFICATION PREFERENCES PAYLOADS (PATCH /api/v1/users/me/notification-preferences)
    fun notificationPrefsPayload(
        channels: List<String>? = listOf("push", "email", "in_app"),
        categories: List<String>? = listOf("POST_LIKED", "POST_COMMENTED", "COMMENT_REPLIED", "USER_FOLLOWED")
    ) = UpdateNotificationPrefsRequestDto(
        channels = channels,
        categories = categories
    )

    val DEFAULT_NOTIFICATION_PREFS = UpdateNotificationPrefsRequestDto(
        channels = listOf("push", "in_app"),
        categories = listOf("POST_LIKED", "POST_COMMENTED", "USER_FOLLOWED")
    )

    val ALL_CHANNELS_NOTIFICATION_PREFS = UpdateNotificationPrefsRequestDto(
        channels = listOf("push", "email", "in_app"),
        categories = listOf("POST_LIKED", "POST_COMMENTED", "COMMENT_REPLIED", "USER_FOLLOWED")
    )
}
