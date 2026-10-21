package com.fyp.basarattradeinvest.domain.model.auth

data class User(
    val id: String,
    val email: String,
    val username: String? = null,
    val fullName: String? = null
)
