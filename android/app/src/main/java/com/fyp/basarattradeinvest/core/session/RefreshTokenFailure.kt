package com.fyp.basarattradeinvest.core.session

class RefreshTokenFailure(
    message: String,
    val statusCode: Int? = null,
    cause: Throwable? = null
) : Exception(message, cause) {
    val isRejected: Boolean
        get() = statusCode == 400 || statusCode == 401 || statusCode == 403 || statusCode == 422
}
