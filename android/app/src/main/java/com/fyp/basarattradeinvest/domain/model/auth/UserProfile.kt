package com.fyp.basarattradeinvest.domain.model.auth

data class UserProfile(
    val id: String,
    val email: String,
    val username: String,
    val fullName: String?,
    val avatarUrl: String?,
    val isActive: Boolean,
    val isVerified: Boolean,
    val riskTolerance: String?,
    val sectorPreferences: List<String>,
    val investmentHorizon: String?,
    val createdAt: String
)
