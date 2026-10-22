package com.fyp.basarattradeinvest.domain.model.auth

data class VerifyResetCodeResult(
    val resetToken: String,
    val expiresIn: Int,
    val tokenType: String,
    val message: String?
)
