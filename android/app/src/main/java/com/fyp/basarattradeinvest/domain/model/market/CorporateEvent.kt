package com.fyp.basarattradeinvest.domain.model.market

data class CorporateEvent(
    val id: String,
    val eventType: String, // e.g. "CASH DIVIDEND", "BOARD MEETING", "RIGHT SHARES", "EARNINGS CALL"
    val symbol: String,
    val companyName: String,
    val eventDate: String,
    val description: String,
    val bookClosure: String = "",
    val sourceNotice: String = "PSX Official Notice",
    val category: String = "All",
    val sourceUrl: String? = null
)
