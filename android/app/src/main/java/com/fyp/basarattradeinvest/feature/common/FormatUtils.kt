package com.fyp.basarattradeinvest.feature.common

import java.text.ParseException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Shared formatting helpers for IPO / ETF screens. Values come straight from the
 * backend (ISO-8601 dates, nullable Doubles). Never fabricate a number: a null is
 * rendered as [NA] or hidden by the caller.
 */
object FormatUtils {

    const val NA = "N/A"

    private const val PARSE_CACHE_MAX = 256

    private val ISO_PATTERNS = listOf(
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
        "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd"
    )

    // These helpers run per list row and repeat across rebind passes, where allocating a
    // SimpleDateFormat for every value was the dominant cost. Formatters are per thread
    // because SimpleDateFormat is not thread-safe.
    private val formatters = object : ThreadLocal<HashMap<String, SimpleDateFormat>>() {
        override fun initialValue(): HashMap<String, SimpleDateFormat> = HashMap()
    }
    private val parsedDates = object : ThreadLocal<HashMap<String, Date?>>() {
        override fun initialValue(): HashMap<String, Date?> = HashMap()
    }

    private fun formatter(pattern: String): SimpleDateFormat =
        formatters.get()!!.computeIfAbsent(pattern) {
            SimpleDateFormat(pattern, Locale.US).apply { isLenient = false }
        }

    fun price(value: Double?): String =
        if (value == null) NA else String.format(Locale.US, "%.2f", value)

    fun pricePk(value: Double?): String =
        if (value == null) NA else "PKR ${String.format(Locale.US, "%.2f", value)}"

    /** Signed percentage, e.g. "+2.14%" / "-0.36%". Null renders [NA]. */
    fun percentSigned(value: Double?): String {
        if (value == null) return NA
        val prefix = if (value >= 0) "+" else ""
        return String.format(Locale.US, "%s%.2f%%", prefix, value)
    }

    /** Plain percentage without sign, e.g. "2.14%". Null renders [NA]. */
    fun percent(value: Double?): String =
        if (value == null) NA else String.format(Locale.US, "%.2f%%", value)

    fun volume(value: Long?): String {
        if (value == null) return NA
        return when {
            value >= 1_000_000_000 -> String.format(Locale.US, "%.2fB", value / 1_000_000_000.0)
            value >= 1_000_000 -> String.format(Locale.US, "%.2fM", value / 1_000_000.0)
            value >= 1_000 -> String.format(Locale.US, "%.1fK", value / 1_000.0)
            else -> value.toString()
        }
    }

    fun largeAmountPkr(value: Double?): String {
        if (value == null) return NA
        return when {
            value >= 1_000_000_000 -> String.format(Locale.US, "PKR %.2fB", value / 1_000_000_000.0)
            value >= 1_000_000 -> String.format(Locale.US, "PKR %.2fM", value / 1_000_000.0)
            else -> String.format(Locale.US, "PKR %,.0f", value)
        }
    }

    /** Full date: "25 Nov 2026". Returns [NA] when null/unparseable. */
    fun dateFull(raw: String?): String {
        val d = parseDate(raw) ?: return NA
        return dateFull(d)
    }

    /** Full date for an already parsed value, so callers avoid a second parse. */
    fun dateFull(date: Date): String = formatter("dd MMM yyyy").format(date)

    /** Short date for table rows: "01 Sep". Returns [NA] when null/unparseable. */
    fun dateShort(raw: String?): String {
        val d = parseDate(raw) ?: return NA
        return formatter("dd MMM").format(d)
    }

    fun parseDate(raw: String?): Date? {
        if (raw.isNullOrBlank()) return null
        val cache = parsedDates.get()!!
        if (cache.containsKey(raw)) return cache[raw]
        if (cache.size >= PARSE_CACHE_MAX) cache.clear()
        var parsed: Date? = null
        for (pattern in ISO_PATTERNS) {
            try {
                parsed = formatter(pattern).parse(raw)
                break
            } catch (_: ParseException) {
                // try next pattern
            }
        }
        cache[raw] = parsed
        return parsed
    }

    /** "UPCOMING" -> "Upcoming", "OPEN_FOR_BOOK_BUILDING" -> "Open For Book Building". */
    fun humanizeEnum(raw: String?): String {
        if (raw.isNullOrBlank()) return NA
        return raw.lowercase(Locale.US)
            .split("_")
            .joinToString(" ") { word ->
                if (word.isEmpty()) word
                else word.replaceFirstChar { it.uppercase(Locale.US) }
            }
    }

    /** IPO lifecycle status -> display label. Falls back to [humanizeEnum] for unknown values. */
    fun ipoStatus(status: String?): String = when (status) {
        "UPCOMING" -> "Upcoming"
        "OPEN_FOR_BOOK_BUILDING" -> "Open for Book Building"
        "OPEN_FOR_PUBLIC_SUBSCRIPTION" -> "Open for Subscription"
        "LISTED" -> "Listed"
        "CLOSED" -> "Closed"
        else -> humanizeEnum(status)
    }

    /** Calendar milestone event type -> display label. Mirrors live API event_type values. */
    fun ipoEventType(eventType: String?): String = when (eventType) {
        "BOOK_BUILDING_START" -> "Book Building Start"
        "BOOK_BUILDING_END" -> "Book Building End"
        "PUBLIC_SUBSCRIPTION_START" -> "Public Subscription Start"
        "PUBLIC_SUBSCRIPTION_END" -> "Public Subscription End"
        "EXCHANGE_LISTING" -> "Exchange Listing"
        "LISTING_DATE" -> "Exchange Listing"
        else -> humanizeEnum(eventType)
    }
}
