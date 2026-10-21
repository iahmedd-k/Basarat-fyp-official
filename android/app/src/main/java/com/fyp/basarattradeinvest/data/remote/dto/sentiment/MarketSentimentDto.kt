package com.fyp.basarattradeinvest.data.remote.dto.sentiment

import com.google.gson.annotations.SerializedName

data class MarketSentimentDto(
    @SerializedName("overall_score")
    val overallScore: Int?,
    @SerializedName("sentiment_label")
    val sentimentLabel: String?,
    @SerializedName("positive_percent")
    val positivePercent: Int?,
    @SerializedName("neutral_percent")
    val neutralPercent: Int?,
    @SerializedName("negative_percent")
    val negativePercent: Int?,
    @SerializedName("news_count")
    val newsCount: Int?,
    @SerializedName("ai_summary")
    val aiSummary: String?
)
