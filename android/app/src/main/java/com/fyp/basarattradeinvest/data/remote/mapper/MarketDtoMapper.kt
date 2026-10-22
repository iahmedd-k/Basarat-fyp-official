package com.fyp.basarattradeinvest.data.remote.mapper

import com.fyp.basarattradeinvest.data.remote.dto.market.ConstituentItemDto
import com.fyp.basarattradeinvest.data.remote.dto.market.IndexConstituentsResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.market.IndexItemDto
import com.fyp.basarattradeinvest.data.remote.dto.market.MarketQuoteItemDto
import com.fyp.basarattradeinvest.data.remote.dto.market.SectorPerformanceItemDto
import com.fyp.basarattradeinvest.data.remote.dto.market.SentimentOverviewDto
import com.fyp.basarattradeinvest.domain.model.market.IndexConstituent
import com.fyp.basarattradeinvest.domain.model.market.IndexConstituents
import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.model.market.SectorPerformance
import java.util.Locale

fun IndexItemDto.toDomain(): MarketIndex {
    val idxName = index ?: code ?: "PSX Index"
    return MarketIndex(
        id = code ?: idxName.lowercase().replace("-", "_"),
        name = idxName,
        code = code.orEmpty(),
        currentPoints = current ?: 0.0,
        changePoints = change ?: 0.0,
        changePercent = changePct ?: 0.0,
        high = high ?: 0.0,
        low = low ?: 0.0,
        intradayPoints = emptyList()
    )
}

fun ConstituentItemDto.toDomain(): IndexConstituent {
    return IndexConstituent(
        symbol = symbol.orEmpty(),
        name = name ?: symbol.orEmpty(),
        ldcp = ldcp ?: 0.0,
        current = current ?: 0.0,
        change = change ?: 0.0,
        changePct = changePct ?: 0.0,
        weightPct = weightPct ?: 0.0,
        indexPoints = indexPoints ?: 0.0,
        volume = volume ?: 0L,
        freeFloatM = freeFloatM ?: 0.0,
        marketCapM = marketCapM ?: 0.0
    )
}

fun IndexConstituentsResponseDto.toDomain(): IndexConstituents {
    return IndexConstituents(
        index = index.orEmpty(),
        code = code.orEmpty(),
        isShariahCompliant = shariahCompliant,
        constituents = constituents?.map { it.toDomain() }.orEmpty()
    )
}

fun MarketQuoteItemDto.toDomain(rank: Int = 1): MarketStock {
    val formattedVolume = formatVolume(volume ?: 0L)
    val priceVal = current ?: ldcp ?: 0.0
    val chgPct = changePct ?: if (change != null && ldcp != null && ldcp > 0) {
        (change / ldcp) * 100.0
    } else 0.0

    return MarketStock(
        rank = rank,
        symbol = symbol.orEmpty(),
        companyName = name ?: symbol.orEmpty(),
        sectorCode = sector ?: "PSX",
        price = priceVal,
        change = change ?: 0.0,
        changePercent = chgPct,
        volume = formattedVolume,
        isShariah = true
    )
}

fun SentimentOverviewDto.toDomain(): MarketSentiment {
    val mood = marketMood ?: "Neutral"
    val adv = advancing ?: 0
    val dec = declining ?: 0
    val unc = unchanged ?: 0
    val total = (adv + dec + unc).coerceAtLeast(1)

    val calculatedScore = if (total > 0) {
        ((adv.toDouble() / total) * 100).toInt().coerceIn(0, 100)
    } else 50

    val posPct = gainersPct?.toInt() ?: ((adv.toDouble() / total) * 100).toInt()
    val negPct = losersPct?.toInt() ?: ((dec.toDouble() / total) * 100).toInt()
    val neuPct = (100 - posPct - negPct).coerceAtLeast(0)

    val ratio = advanceDeclineRatio ?: if (dec > 0) adv.toDouble() / dec else adv.toDouble()

    return MarketSentiment(
        overallScore = calculatedScore,
        sentimentLabel = mood,
        positivePercent = posPct,
        neutralPercent = neuPct,
        negativePercent = negPct,
        newsCount = 0,
        aiSummary = "Market mood is $mood with $adv advancing, $dec declining, and $unc unchanged stocks.",
        advanceDeclineRatio = ratio,
        advancing = adv,
        declining = dec,
        unchanged = unc
    )
}

fun SectorPerformanceItemDto.toDomain(): SectorPerformance {
    val pct = avgChangePct ?: 0.0
    val sec = sector ?: "General"
    return SectorPerformance(
        id = sec.lowercase().replace(" ", "_"),
        sectorName = sec,
        changePercent = pct,
        volume = "${companies ?: 0} Cos",
        isPositive = pct >= 0
    )
}

fun com.fyp.basarattradeinvest.data.remote.dto.market.SectorPerformanceDetailDto.toDomain(): SectorPerformance {
    val pct = avgChangePct ?: 0.0
    val sec = sector ?: "General"
    val volStr = when {
        totalVolume != null && totalVolume > 0 -> formatVolume(totalVolume)
        companies != null -> "${companies} Cos"
        else -> ""
    }
    return SectorPerformance(
        id = sec.lowercase().replace(" ", "_"),
        sectorName = sec,
        changePercent = pct,
        volume = volStr,
        isPositive = pct >= 0
    )
}

private fun formatVolume(vol: Long): String {
    return when {
        vol >= 1_000_000_000 -> String.format(Locale.US, "%.2fB", vol / 1_000_000_000.0)
        vol >= 1_000_000 -> String.format(Locale.US, "%.2fM", vol / 1_000_000.0)
        vol >= 1_000 -> String.format(Locale.US, "%.1fK", vol / 1_000.0)
        else -> vol.toString()
    }
}
