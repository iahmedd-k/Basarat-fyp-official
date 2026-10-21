package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.alerts.AlertResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.alerts.QuickAlertRuleCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.alerts.QuickAlertRuleResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit API interface for quick stock alerts and triggered alert history.
 * Source of truth: OpenAPI /api/v1/openapi.json
 */
interface AlertsApiService {

    /**
     * Create the backend-managed 1-click price alert for a stock.
     * HTTP 201 on success; percentage and direction use backend defaults when omitted.
     */
    @POST("api/v1/alerts/quick-rule")
    suspend fun createQuickAlertRule(
        @Body request: QuickAlertRuleCreateDto
    ): Response<QuickAlertRuleResponseDto>

    /**
     * Get user's triggered alerts / notification history.
     */
    @GET("api/v1/alerts")
    suspend fun getAlerts(
        @Query("page") page: Int? = null,
        @Query("limit") limit: Int? = null,
        @Query("unread_only") unreadOnly: Boolean? = null
    ): Response<List<AlertResponseDto>>

    /**
     * Mark a triggered alert as read.
     */
    @PATCH("api/v1/alerts/{alert_id}/read")
    suspend fun markAlertAsRead(
        @Path("alert_id") alertId: String
    ): Response<Unit>
}
