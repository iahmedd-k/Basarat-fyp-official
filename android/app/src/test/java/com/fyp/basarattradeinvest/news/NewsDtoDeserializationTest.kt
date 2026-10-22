package com.fyp.basarattradeinvest.news

import com.fyp.basarattradeinvest.data.mapper.NewsDtoMapper
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsArticleResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.news.NewsListResponseDto
import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class NewsDtoDeserializationTest {

    private val gson = Gson()

    @Test
    fun testDeserializeNewsWithObjectSentiment() {
        val json = """
            {
                "items": [
                    {
                        "id": "item1",
                        "title": "Systems Ltd Expansion",
                        "sentiment": {
                            "label": "neutral",
                            "score": null,
                            "method": "finbert"
                        },
                        "published_at": "2026-09-23T19:00:00+00:00",
                        "created_at": "2026-09-23T20:16:16.402795+00:00"
                    },
                    {
                        "id": "item2",
                        "title": "OGDC Profit Surge",
                        "sentiment": {
                            "label": "bullish",
                            "score": 0.85,
                            "method": "eps_rule"
                        },
                        "published_at": "2026-09-23T20:00:00+00:00",
                        "created_at": "2026-09-23T21:16:16.402795+00:00"
                    }
                ],
                "total": 2,
                "has_more": false,
                "row": "news"
            }
        """.trimIndent()

        val response = gson.fromJson(json, NewsListResponseDto::class.java)
        assertNotNull(response)
        assertEquals(2, response.items?.size)

        val item1 = response.items!![0]
        assertEquals("neutral", item1.sentiment?.label)
        assertNull(item1.sentiment?.score)
        assertEquals("finbert", item1.sentiment?.method)

        val domain1 = NewsDtoMapper.mapArticleDtoToDomain(item1)
        assertEquals("Neutral", domain1.sentimentLabel)
        assertEquals(0.0, domain1.sentimentScore, 0.001)

        val item2 = response.items!![1]
        assertEquals("bullish", item2.sentiment?.label)
        assertEquals(0.85, item2.sentiment?.score ?: 0.0, 0.001)
        assertEquals("eps_rule", item2.sentiment?.method)

        val domain2 = NewsDtoMapper.mapArticleDtoToDomain(item2)
        assertEquals("Bullish", domain2.sentimentLabel)
        assertEquals(0.85, domain2.sentimentScore, 0.001)
    }

    @Test
    fun testDeserializeNewsWithNullSentiment() {
        val json = """
            {
                "items": [
                    {
                        "id": "item3",
                        "title": "PSX Market Notice",
                        "sentiment": null,
                        "published_at": "2026-09-23T19:00:00+00:00",
                        "created_at": "2026-09-23T20:16:16.402795+00:00"
                    }
                ],
                "total": 1,
                "has_more": false,
                "row": "news"
            }
        """.trimIndent()

        val response = gson.fromJson(json, NewsListResponseDto::class.java)
        assertNotNull(response)
        val item3 = response.items!![0]
        assertNull(item3.sentiment)

        val domain3 = NewsDtoMapper.mapArticleDtoToDomain(item3)
        assertEquals("Neutral", domain3.sentimentLabel)
        assertEquals(0.0, domain3.sentimentScore, 0.001)
    }

    @Test
    fun testDeserializeNewsWithStringSentiment() {
        val json = """
            {
                "items": [
                    {
                        "id": "item4",
                        "title": "Cement Sector Bearish Trend",
                        "sentiment": "bearish",
                        "published_at": "2026-09-23T19:00:00+00:00",
                        "created_at": "2026-09-23T20:16:16.402795+00:00"
                    }
                ],
                "total": 1,
                "has_more": false,
                "row": "news"
            }
        """.trimIndent()

        val response = gson.fromJson(json, NewsListResponseDto::class.java)
        assertNotNull(response)
        val item4 = response.items!![0]
        assertEquals("bearish", item4.sentiment?.label)

        val domain4 = NewsDtoMapper.mapArticleDtoToDomain(item4)
        assertEquals("Bearish", domain4.sentimentLabel)
        assertEquals(-0.50, domain4.sentimentScore, 0.001)
    }
}
