package com.fyp.basarattradeinvest.data.remote.dto.user

import com.google.gson.annotations.SerializedName

data class UserSummaryDto(
    @SerializedName("id")
    val id: Any,

    @SerializedName("email")
    val email: String,

    @SerializedName("username")
    val username: String? = null,

    @SerializedName("full_name")
    val fullName: String? = null
)
