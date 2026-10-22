package com.fyp.basarattradeinvest.data.remote.mapper

import com.fyp.basarattradeinvest.data.remote.dto.market.MarketIndexDto
import com.fyp.basarattradeinvest.data.remote.dto.market.MarketOverviewDto
import com.fyp.basarattradeinvest.data.remote.dto.market.MarketStockDto
import com.fyp.basarattradeinvest.data.remote.dto.sentiment.MarketSentimentDto
import com.fyp.basarattradeinvest.data.remote.dto.market.SectorPerformanceDto
import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.market.MarketOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.model.market.SectorPerformance

fun MarketIndexDto.toDomain(): MarketIndex {
    return MarketIndex(
        id = id.orEmpty(),
        name = name ?: "PSX Index",
        currentPoints = currentPoints ?: 0.0,
        changePoints = changePoints ?: 0.0,
        changePercent = changePercent ?: 0.0,
        intradayPoints = intradayPoints ?: emptyList()
    )
}

fun MarketOverviewDto.toDomain(): MarketOverview {
    return MarketOverview(
        tradedValue = tradedValue ?: "0.00B",
        tradedVolume = tradedVolume ?: "0.00M",
        totalTrades = totalTrades ?: "0",
        upCount = upCount ?: 0,
        unchangedCount = unchangedCount ?: 0,
        downCount = downCount ?: 0,
        totalStocks = totalStocks ?: 0
    )
}

fun MarketStockDto.toDomain(): MarketStock {
    return MarketStock(
        rank = rank ?: 1,
        symbol = symbol ?: "---",
        companyName = companyName ?: "Company",
        sectorCode = sectorCode ?: "PSX",
        price = price ?: 0.0,
        change = change ?: 0.0,
        changePercent = changePercent ?: 0.0,
        volume = volume ?: "",
        isShariah = isShariah ?: true
    )
}

fun MarketSentimentDto.toDomain(): MarketSentiment {
    return MarketSentiment(
        overallScore = overallScore ?: 65,
        sentimentLabel = sentimentLabel ?: "Bullish",
        positivePercent = positivePercent ?: 58,
        neutralPercent = neutralPercent ?: 24,
        negativePercent = negativePercent ?: 18,
        newsCount = newsCount ?: 142,
        aiSummary = aiSummary ?: "PSX market sentiment is predominantly bullish, led by Technology and Energy earnings momentum."
    )
}

fun SectorPerformanceDto.toDomain(): SectorPerformance {
    val pct = changePercent ?: 0.0
    return SectorPerformance(
        id = id.orEmpty(),
        sectorName = sectorName ?: "General",
        changePercent = pct,
        volume = volume ?: "0M",
        isPositive = pct >= 0
    )
}

