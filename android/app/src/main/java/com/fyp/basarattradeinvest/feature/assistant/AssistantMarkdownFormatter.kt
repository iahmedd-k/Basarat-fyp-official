package com.fyp.basarattradeinvest.feature.assistant

import android.graphics.Typeface
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan

/**
 * Lightweight native Markdown formatter for AI Assistant responses.
 * Formats bold text (**bold**), headers (### Header), and bullet points without external dependencies.
 */
object AssistantMarkdownFormatter {

    // format() runs per message per rebind, so the patterns and span are built once, not per line.
    private val HEADER_REGEX = Regex("^(#{1,3})\\s+(.+)$")
    private val BOLD_REGEX = Regex("\\*\\*(.*?)\\*\\*")
    private val BOLD_SPAN = StyleSpan(Typeface.BOLD)

    fun format(text: String): CharSequence {
        if (text.isEmpty()) return ""
        return try {
            formatSpannable(text)
        } catch (_: Throwable) {
            formatPlainText(text)
        }
    }

    private fun formatSpannable(text: String): CharSequence {
        val ssb = SpannableStringBuilder()
        val lines = text.split("\n")

        for (i in lines.indices) {
            val line = lines[i]

            // Check for headers: e.g. ### Header or ## Header
            val headerMatch = HEADER_REGEX.find(line)
            if (headerMatch != null) {
                val headerLevel = headerMatch.groupValues[1].length
                val headerText = headerMatch.groupValues[2]
                val start = ssb.length
                appendInlineFormatted(ssb, headerText)
                val end = ssb.length
                val sizeMultiplier = if (headerLevel == 1) 1.25f else if (headerLevel == 2) 1.15f else 1.08f
                ssb.setSpan(BOLD_SPAN, start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
                ssb.setSpan(RelativeSizeSpan(sizeMultiplier), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            } else if (line.trimStart().startsWith("- ") || line.trimStart().startsWith("* ")) {
                val bulletContent = line.trimStart().drop(2)
                ssb.append("• ")
                appendInlineFormatted(ssb, bulletContent)
            } else {
                appendInlineFormatted(ssb, line)
            }

            if (i < lines.size - 1) {
                ssb.append("\n")
            }
        }

        return ssb
    }

    private fun appendInlineFormatted(ssb: SpannableStringBuilder, text: String) {
        var cursor = 0
        val matches = BOLD_REGEX.findAll(text)

        for (match in matches) {
            val range = match.range
            if (range.first > cursor) {
                ssb.append(text.substring(cursor, range.first))
            }
            val boldText = match.groupValues[1]
            val spanStart = ssb.length
            ssb.append(boldText)
            val spanEnd = ssb.length
            ssb.setSpan(BOLD_SPAN, spanStart, spanEnd, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            cursor = range.last + 1
        }

        if (cursor < text.length) {
            ssb.append(text.substring(cursor))
        }
    }

    private fun formatPlainText(text: String): String {
        val lines = text.split("\n")
        return lines.joinToString("\n") { line ->
            var formatted = line
            val headerMatch = HEADER_REGEX.find(formatted)
            if (headerMatch != null) {
                formatted = headerMatch.groupValues[2]
            } else if (formatted.trimStart().startsWith("- ") || formatted.trimStart().startsWith("* ")) {
                formatted = "• " + formatted.trimStart().drop(2)
            }
            formatted.replace(BOLD_REGEX, "$1")
        }
    }
}
