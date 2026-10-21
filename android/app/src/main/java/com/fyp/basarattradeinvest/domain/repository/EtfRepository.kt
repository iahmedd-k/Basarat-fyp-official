package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.etf.EtfHistoryEntry
import com.fyp.basarattradeinvest.domain.model.etf.EtfItem
import com.fyp.basarattradeinvest.domain.model.etf.EtfPerformance
import com.fyp.basarattradeinvest.domain.model.etf.EtfsResult

interface EtfRepository {
    suspend fun getEtfs(): Result<EtfsResult>
    suspend fun getEtfDetail(symbol: String): Result<EtfItem>
    suspend fun getEtfHistory(symbol: String, timeframe: String): Result<List<EtfHistoryEntry>>
    suspend fun getEtfPerformance(symbol: String): Result<EtfPerformance>
}
