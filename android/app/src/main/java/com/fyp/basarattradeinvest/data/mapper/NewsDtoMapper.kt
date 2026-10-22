package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.news.EventResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsArticleResponseDto
import com.fyp.basarattradeinvest.domain.model.market.CorporateEvent
import com.fyp.basarattradeinvest.domain.model.news.NewsArticle
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

object NewsDtoMapper {

    // Mapping runs once per article, so the formatters and the event-date regex are reused
    // instead of being allocated for every value. They are kept per thread because
    // SimpleDateFormat is not thread-safe.
    private val formatters = object : ThreadLocal<HashMap<String, SimpleDateFormat>>() {
        override fun initialValue(): HashMap<String, SimpleDateFormat> = HashMap()
    }
    private val eventDatePattern = Regex("\\d{4}-\\d{2}-\\d{2}")

    private fun formatter(key: String, pattern: String, utc: Boolean = false): SimpleDateFormat =
        formatters.get()!!.computeIfAbsent(key) {
            SimpleDateFormat(pattern, Locale.US).apply {
                if (utc) timeZone = TimeZone.getTimeZone("UTC")
            }
        }

    fun mapArticleDtoToDomain(dto: NewsArticleResponseDto): NewsArticle {
        val primarySymbol = dto.symbols?.firstOrNull()?.symbol ?: "PSX"
        val allSymbols = dto.symbols?.map { it.symbol } ?: emptyList()
        val sourceName = dto.source?.name ?: dto.source?.key ?: "PSX News"
        val sentimentObj = dto.sentiment
        val sentimentStr = sentimentObj?.label?.lowercase(Locale.ROOT)
        val label = when (sentimentStr) {
            "bullish", "positive" -> "Bullish"
            "bearish", "negative" -> "Bearish"
            else -> "Neutral"
        }
        // Only the backend's own score is shown; an unlabelled article stays neutral at zero.
        val score = sentimentObj?.score ?: when (label) {
            "Bullish" -> 0.5
            "Bearish" -> -0.5
            else -> 0.0
        }
        val isDiv = dto.eventType?.contains("dividend", ignoreCase = true) == true ||
                dto.title.contains("dividend", ignoreCase = true) ||
                (dto.summary?.contains("dividend", ignoreCase = true) == true)

        val relativeTime = formatRelativeTime(dto.publishedAt ?: dto.createdAt)

        return NewsArticle(
            id = dto.id,
            symbol = primarySymbol,
            hasDividend = isDiv,
            source = sourceName,
            timestamp = relativeTime,
            sentimentScore = score,
            sentimentLabel = label,
            headline = dto.title,
            snippet = dto.summary ?: dto.title,
            category = dto.eventType ?: "All",
            url = dto.url,
            externalUrl = dto.externalUrl,
            isOfficial = dto.isOfficial ?: false,
            symbols = allSymbols,
            publishedAt = dto.publishedAt ?: dto.createdAt
        )
    }

    fun mapEventDtoToDomain(dto: EventResponseDto): CorporateEvent {
        val sym = dto.symbol ?: "PSX"
        val comp = dto.companyName ?: sym
        val formattedDate = formatEventDate(dto.eventDate)
        val eventTypeUpper = dto.eventType.uppercase(Locale.ROOT)
            .replace("_", " ")

        return CorporateEvent(
            id = dto.id,
            eventType = eventTypeUpper,
            symbol = sym,
            companyName = comp,
            eventDate = formattedDate,
            description = dto.title.ifBlank { dto.description.orEmpty() },
            bookClosure = dto.description.orEmpty(),
            sourceNotice = dto.source ?: "PSX Official Notice",
            category = dto.eventType,
            sourceUrl = dto.sourceUrl
        )
    }

    internal fun formatRelativeTime(dateString: String?): String {
        if (dateString.isNullOrBlank()) return "Recent"
        try {
            val isoFormat = formatter("iso-utc", "yyyy-MM-dd'T'HH:mm:ss", utc = true)
            // Strip fractional seconds if present
            val cleaned = dateString.substringBefore(".").substringBefore("Z").substringBefore("+")
            val parsedDate = isoFormat.parse(cleaned) ?: return dateString
            val diffMs = System.currentTimeMillis() - parsedDate.time
            val diffMin = diffMs / (60 * 1000)
            val diffHours = diffMin / 60
            val diffDays = diffHours / 24

            return when {
                diffMin < 1 -> "Just now"
                diffMin < 60 -> "${diffMin}m ago"
                diffHours < 24 -> "${diffHours}h ago"
                diffDays < 7 -> "${diffDays}d ago"
                else -> {
                    formatter("display-date", "MMM dd, yyyy").format(parsedDate)
                }
            }
        } catch (_: Exception) {
            return dateString
        }
    }

    internal fun formatEventDate(dateString: String): String {
        if (dateString.isBlank()) return "Upcoming"
        try {
            // Check if format is YYYY-MM-DD
            if (dateString.matches(eventDatePattern)) {
                val inputFormat = formatter("event-input-date", "yyyy-MM-dd")
                val outputFormat = formatter("display-date", "MMM dd, yyyy")
                val date = inputFormat.parse(dateString)
                if (date != null) {
                    return outputFormat.format(date)
                }
            }
        } catch (_: Exception) {
            // Keep original on parse failure
        }
        return dateString
    }
}
