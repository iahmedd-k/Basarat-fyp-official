package com.fyp.basarattradeinvest.core.network

/**
 * DevTokenConfig
 *
 * Legacy development token holder. AuthInterceptor intentionally does not send this token;
 * protected requests must use the access token from the user's stored session.
 */
object DevTokenConfig {
    var DEV_ACCESS_TOKEN: String = ""
}
