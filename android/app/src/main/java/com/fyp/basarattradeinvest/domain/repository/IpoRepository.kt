package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.ipo.IpoCalendarEvent
import com.fyp.basarattradeinvest.domain.model.ipo.IpoItem
import com.fyp.basarattradeinvest.domain.model.ipo.IpoPerformanceSummary

interface IpoRepository {
    suspend fun getIpos(): Result<List<IpoItem>>
    suspend fun getIpoDetail(symbol: String): Result<IpoItem>
    suspend fun getIpoCalendar(): Result<List<IpoCalendarEvent>>
    suspend fun getIpoPerformance(): Result<IpoPerformanceSummary>
}
