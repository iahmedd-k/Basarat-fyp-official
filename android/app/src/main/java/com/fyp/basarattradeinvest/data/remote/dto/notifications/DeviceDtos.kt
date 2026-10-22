package com.fyp.basarattradeinvest.data.remote.dto.notifications

import com.google.gson.annotations.SerializedName

data class DeviceRegisterRequestDto(
    @SerializedName("fcm_token") val fcmToken: String,
    @SerializedName("platform") val platform: String = "android",
    @SerializedName("device_name") val deviceName: String
)

data class DeviceRegisterResponseDto(
    @SerializedName("id") val id: String
)
