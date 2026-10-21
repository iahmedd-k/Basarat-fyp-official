package com.fyp.basarattradeinvest.data.remote.dto.news

import com.google.gson.JsonDeserializationContext
import com.google.gson.JsonDeserializer
import com.google.gson.JsonElement
import com.google.gson.annotations.JsonAdapter
import com.google.gson.annotations.SerializedName
import java.lang.reflect.Type

/**
 * News and Events DTOs matching backend OpenAPI schemas.
 * Reference: http://16.16.26.247:8000/api/v1/openapi.json
 */

data class NewsListResponseDto(
    @SerializedName("items")
    val items: List<NewsArticleResponseDto>? = null,

    @SerializedName("next_cursor")
    val nextCursor: String? = null,

    @SerializedName("has_more")
    val hasMore: Boolean? = null,

    @SerializedName("row")
    val row: String? = null,

    @SerializedName("last_updated_at")
    val lastUpdatedAt: String? = null,

    @SerializedName("empty_reason")
    val emptyReason: String? = null,

    @SerializedName("total")
    val total: Int? = null
)

data class NewsArticleResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("title")
    val title: String,

    @SerializedName("url")
    val url: String? = null,

    @SerializedName("external_url")
    val externalUrl: String? = null,

    @SerializedName("source")
    val source: SourceInfoDto? = null,

    @SerializedName("is_official")
    val isOfficial: Boolean? = null,

    @SerializedName("summary")
    val summary: String? = null,

    @SerializedName("symbols")
    val symbols: List<SymbolInfoDto>? = null,

    @SerializedName("event_type")
    val eventType: String? = null,

    @SerializedName("sentiment")
    val sentiment: SentimentInfoDto? = null,

    @SerializedName("impact_score")
    val impactScore: Double? = null,

    @SerializedName("published_at")
    val publishedAt: String? = null,

    @SerializedName("created_at")
    val createdAt: String? = null
)

@JsonAdapter(SentimentInfoDeserializer::class)
data class SentimentInfoDto(
    @SerializedName("label")
    val label: String? = null,

    @SerializedName("score")
    val score: Double? = null,

    @SerializedName("method")
    val method: String? = null
)

class SentimentInfoDeserializer : JsonDeserializer<SentimentInfoDto?> {
    override fun deserialize(
        json: JsonElement?,
        typeOfT: Type?,
        context: JsonDeserializationContext?
    ): SentimentInfoDto? {
        if (json == null || json.isJsonNull) return null
        return try {
            if (json.isJsonObject) {
                val obj = json.asJsonObject
                val label = if (obj.has("label") && !obj.get("label").isJsonNull) {
                    obj.get("label").asString
                } else null

                val score = if (obj.has("score") && !obj.get("score").isJsonNull) {
                    try {
                        obj.get("score").asDouble
                    } catch (_: Exception) {
                        null
                    }
                } else null

                val method = if (obj.has("method") && !obj.get("method").isJsonNull) {
                    obj.get("method").asString
                } else null

                SentimentInfoDto(label = label, score = score, method = method)
            } else if (json.isJsonPrimitive) {
                SentimentInfoDto(label = json.asString, score = null, method = null)
            } else {
                null
            }
        } catch (_: Exception) {
            null
        }
    }
}

data class SourceInfoDto(
    @SerializedName("key")
    val key: String? = null,

    @SerializedName("name")
    val name: String? = null,

    @SerializedName("type")
    val type: String? = null
)

data class SymbolInfoDto(
    @SerializedName("symbol")
    val symbol: String,

    @SerializedName("name")
    val name: String? = null
)

data class NewsRefreshResponseDto(
    @SerializedName("status")
    val status: String,

    @SerializedName("last_updated")
    val lastUpdated: String? = null,

    @SerializedName("refresh_available")
    val refreshAvailable: Boolean? = null,

    @SerializedName("next_refresh_at")
    val nextRefreshAt: String? = null,

    @SerializedName("articles_inserted")
    val articlesInserted: Int? = null,

    @SerializedName("market_status")
    val marketStatus: Any? = null,

    @SerializedName("retry_after_seconds")
    val retryAfterSeconds: Int? = null
)

data class NewsRefreshStatusResponseDto(
    @SerializedName("state")
    val state: String, // "idle" | "running" | "completed" | "failed"

    @SerializedName("last_success_at")
    val lastSuccessAt: String? = null,

    @SerializedName("new_articles")
    val newArticles: Int? = null
)

data class MarketStatusResponseDto(
    @SerializedName("current_time_pkt")
    val currentTimePkt: String? = null,

    @SerializedName("market_window")
    val marketWindow: String? = null,

    @SerializedName("is_open")
    val isOpen: Boolean? = null,

    @SerializedName("next_window")
    val nextWindow: String? = null,

    @SerializedName("ingestion_status")
    val ingestionStatus: String? = null
)

data class SourcesResponseDto(
    @SerializedName("sources")
    val sources: List<SourceHealthResponseDto>? = null
)

data class SourceHealthResponseDto(
    @SerializedName("key")
    val key: String,

    @SerializedName("name")
    val name: String,

    @SerializedName("type")
    val type: String,

    @SerializedName("last_success_at")
    val lastSuccessAt: String? = null,

    @SerializedName("last_error")
    val lastError: String? = null,

    @SerializedName("consecutive_failures")
    val consecutiveFailures: Int = 0,

    @SerializedName("healthy")
    val healthy: Boolean = true
)

data class EventsCalendarResponseDto(
    @SerializedName("items")
    val items: List<EventResponseDto>? = null,

    @SerializedName("total")
    val total: Int? = null
)

data class EventResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("event_type")
    val eventType: String,

    @SerializedName("symbol")
    val symbol: String? = null,

    @SerializedName("company_name")
    val companyName: String? = null,

    @SerializedName("event_date")
    val eventDate: String,

    @SerializedName("title")
    val title: String,

    @SerializedName("description")
    val description: String? = null,

    @SerializedName("source")
    val source: String? = null,

    @SerializedName("source_url")
    val sourceUrl: String? = null
)
