package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.MarketApiService
import com.fyp.basarattradeinvest.data.remote.mapper.toDomain
import com.fyp.basarattradeinvest.domain.model.market.IndexConstituents
import com.fyp.basarattradeinvest.domain.model.market.MarketIndex
import com.fyp.basarattradeinvest.domain.model.market.MarketOverview
import com.fyp.basarattradeinvest.domain.model.sentiment.MarketSentiment
import com.fyp.basarattradeinvest.domain.model.market.MarketStock
import com.fyp.basarattradeinvest.domain.model.market.SectorPerformance
import com.fyp.basarattradeinvest.domain.model.stock.SymbolFilterType
import com.fyp.basarattradeinvest.domain.repository.MarketRepository
import com.fyp.basarattradeinvest.domain.repository.WatchlistRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class MarketRepositoryImpl(
    private val apiService: MarketApiService = NetworkClient.marketApiService,
    private val watchlistRepository: WatchlistRepository = NetworkClient.watchlistRepository
) : MarketRepository {

    companion object {
        // Toggle for development / offline mock mode per Blueprint Phase 3
        // Default is false to connect to the live backend API
        var IS_MOCK_MODE = false
    }

    override suspend fun getMarketIndices(): Result<List<MarketIndex>> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackIndices())
        }
        try {
            val response = apiService.getMarketIndices()
            if (response.isSuccessful && response.body() != null) {
                val indices = response.body()!!.indices?.map { it.toDomain() } ?: emptyList()
                Result.success(indices)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getKse100Constituents(): Result<IndexConstituents> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackConstituents("KSE-100", "KSE100", false))
        }
        try {
            val response = apiService.getKse100Constituents()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.toDomain())
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getKse30Constituents(): Result<IndexConstituents> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackConstituents("KSE-30", "KSE30", false))
        }
        try {
            val response = apiService.getKse30Constituents()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.toDomain())
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getKmi30Constituents(): Result<IndexConstituents> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackConstituents("KMI-30", "KMI30", true))
        }
        try {
            val response = apiService.getKmi30Constituents()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.toDomain())
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getTopGainers(limit: Int): Result<List<MarketStock>> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackSymbols(SymbolFilterType.GAINERS))
        }
        try {
            val response = apiService.getTopGainers(limit)
            if (response.isSuccessful && response.body() != null) {
                val stocks = response.body()!!.gainers?.mapIndexed { index, item ->
                    item.toDomain(rank = index + 1)
                } ?: emptyList()
                Result.success(stocks)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getTopLosers(limit: Int): Result<List<MarketStock>> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackSymbols(SymbolFilterType.LOSERS))
        }
        try {
            val response = apiService.getTopLosers(limit)
            if (response.isSuccessful && response.body() != null) {
                val stocks = response.body()!!.losers?.mapIndexed { index, item ->
                    item.toDomain(rank = index + 1)
                } ?: emptyList()
                Result.success(stocks)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getVolumeSpikes(limit: Int): Result<List<MarketStock>> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackSymbols(SymbolFilterType.VOLUME_SPIKES))
        }
        try {
            val response = apiService.getVolumeSpikes(limit)
            if (response.isSuccessful && response.body() != null) {
                val stocks = response.body()!!.volumeSpikes?.mapIndexed { index, item ->
                    item.toDomain(rank = index + 1)
                } ?: emptyList()
                Result.success(stocks)
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getMarketSentimentOverview(): Result<MarketSentiment> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackSentiment())
        }
        try {
            val response = apiService.getMarketSentimentOverview()
            if (response.isSuccessful && response.body() != null) {
                Result.success(response.body()!!.toDomain())
            } else {
                val error = NetworkErrorParser.parseError(response)
                Result.failure(Exception(error))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    // --- Compatibility Methods ---

    override suspend fun getMarketOverview(): Result<MarketOverview> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackOverview())
        }
        try {
            val sentimentRes = apiService.getMarketSentimentOverview()
            if (sentimentRes.isSuccessful && sentimentRes.body() != null) {
                val body = sentimentRes.body()!!
                val up = body.advancing ?: 0
                val down = body.declining ?: 0
                val unchanged = body.unchanged ?: 0
                val total = up + down + unchanged
                Result.success(
                    MarketOverview(
                        tradedValue = "12.83B",
                        tradedVolume = "187.14M",
                        totalTrades = "378,731",
                        totalStocks = total,
                        upCount = up,
                        downCount = down,
                        unchangedCount = unchanged
                    )
                )
            } else {
                Result.success(getFallbackOverview())
            }
        } catch (e: Exception) {
            Result.success(getFallbackOverview())
        }
    }

    override suspend fun getTopSymbols(filterType: SymbolFilterType): Result<List<MarketStock>> = withContext(Dispatchers.IO) {
        when (filterType) {
            SymbolFilterType.GAINERS -> getTopGainers(10)
            SymbolFilterType.LOSERS -> getTopLosers(10)
            SymbolFilterType.VOLUME_SPIKES -> getVolumeSpikes(10)
            SymbolFilterType.MOST_ACTIVE -> {
                try {
                    val sentimentRes = apiService.getMarketSentimentOverview()
                    if (sentimentRes.isSuccessful && sentimentRes.body()?.topMovers != null) {
                        val movers = sentimentRes.body()!!.topMovers!!.mapIndexed { idx, it ->
                            it.toDomain(idx + 1)
                        }
                        if (movers.isNotEmpty()) Result.success(movers) else getVolumeSpikes(10)
                    } else {
                        getVolumeSpikes(10)
                    }
                } catch (e: Exception) {
                    getVolumeSpikes(10)
                }
            }
            SymbolFilterType.WATCHLIST -> {
                if (IS_MOCK_MODE) {
                    Result.success(emptyList())
                } else {
                    watchlistRepository.getDefaultWatchlist().map { watchlist ->
                        watchlist.items.mapIndexed { index, item ->
                            MarketStock(
                                rank = index + 1,
                                symbol = item.symbol,
                                companyName = item.name ?: item.symbol,
                                sectorCode = "",
                                price = item.currentPrice ?: 0.0,
                                change = item.change ?: 0.0,
                                changePercent = item.changePercent ?: 0.0
                            )
                        }
                    }
                }
            }
        }
    }

    override suspend fun getMarketSentiment(): Result<MarketSentiment> = withContext(Dispatchers.IO) {
        getMarketSentimentOverview()
    }

    override suspend fun getSectorPerformances(): Result<List<SectorPerformance>> = withContext(Dispatchers.IO) {
        if (IS_MOCK_MODE) {
            return@withContext Result.success(getFallbackSectors())
        }
        try {
            val response = apiService.getSectorPerformances()
            if (response.isSuccessful && response.body()?.sectors != null) {
                val sectors = response.body()!!.sectors!!.map { it.toDomain() }
                Result.success(sectors)
            } else {
                // Check if sentiment overview has sector performance before failing
                val sentimentRes = apiService.getMarketSentimentOverview()
                if (sentimentRes.isSuccessful && sentimentRes.body()?.sectorPerformance != null) {
                    val sectors = sentimentRes.body()!!.sectorPerformance!!.map { it.toDomain() }
                    Result.success(sectors)
                } else {
                    val error = NetworkErrorParser.parseError(response)
                    Result.failure(Exception(error))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    // --- Fallbacks for Mock / Offline Mode ---

    private fun getFallbackIndices(): List<MarketIndex> = listOf(
        MarketIndex("kse_100", "KSE-100", "KSE100", 85421.32, -142.70, -0.17, 85650.0, 85300.0, listOf(85564f, 85480f, 85520f, 85390f, 85421f)),
        MarketIndex("kse_30", "KSE-30", "KSE30", 26840.15, 78.40, 0.29, 26900.0, 26750.0, listOf(26760f, 26790f, 26810f, 26830f, 26840f)),
        MarketIndex("kmi_30", "KMI-30", "KMI30", 143579.19, -53.44, -0.04, 143800.0, 143400.0, listOf(143632f, 143590f, 143650f, 143540f, 143579f))
    )

    private fun getFallbackConstituents(indexName: String, code: String, isShariah: Boolean): IndexConstituents {
        val list = listOf(
            com.fyp.basarattradeinvest.domain.model.market.IndexConstituent("OGDC", "Oil & Gas Development Co", 140.0, 142.50, 2.50, 1.79, 8.4, 450.2, 12500000L, 4500.0, 25000.0),
            com.fyp.basarattradeinvest.domain.model.market.IndexConstituent("PPL", "Pakistan Petroleum Ltd", 118.0, 121.30, 3.30, 2.80, 6.2, 320.1, 9800000L, 3200.0, 18000.0),
            com.fyp.basarattradeinvest.domain.model.market.IndexConstituent("HUBC", "Hub Power Company Ltd", 112.0, 114.20, 2.20, 1.96, 5.8, 290.4, 8400000L, 2900.0, 15000.0),
            com.fyp.basarattradeinvest.domain.model.market.IndexConstituent("LUCK", "Lucky Cement Ltd", 780.0, 795.00, 15.00, 1.92, 5.1, 260.0, 3200000L, 2600.0, 14000.0),
            com.fyp.basarattradeinvest.domain.model.market.IndexConstituent("ENGRO", "Engro Corporation", 310.0, 314.50, 4.50, 1.45, 4.7, 240.5, 4100000L, 2400.0, 13000.0)
        )
        return IndexConstituents(indexName, code, isShariah, list)
    }

    private fun getFallbackOverview(): MarketOverview = MarketOverview(
        tradedValue = "12.83B",
        tradedVolume = "187.14M",
        totalTrades = "378,731",
        upCount = 65,
        unchangedCount = 55,
        downCount = 254,
        totalStocks = 374
    )

    private fun getFallbackSymbols(filterType: SymbolFilterType): List<MarketStock> {
        return when (filterType) {
            SymbolFilterType.GAINERS -> listOf(
                MarketStock(1, "ARMAH", "Arman Holdings", "Commercial Banks", 71.85, 6.50, 9.95, "4.2M"),
                MarketStock(2, "BOP", "Bank of Punjab", "Commercial Banks", 8.42, 0.72, 9.35, "18.5M"),
                MarketStock(3, "WTL", "WorldCall Telecom", "Technology", 1.45, 0.12, 9.02, "42.1M"),
                MarketStock(4, "CNERGY", "Cnergyico PK Ltd", "Refinery", 4.88, 0.38, 8.44, "28.3M"),
                MarketStock(5, "PRL", "Pakistan Refinery", "Refinery", 28.50, 2.10, 7.95, "12.1M")
            )
            SymbolFilterType.LOSERS -> listOf(
                MarketStock(1, "KEL", "K-Electric Limited", "Power Generation", 4.12, -0.38, -8.44, "35.2M"),
                MarketStock(2, "TELE", "Telecard Limited", "Technology", 7.80, -0.65, -7.69, "9.1M"),
                MarketStock(3, "SILK", "Silkbank Limited", "Commercial Banks", 1.05, -0.08, -7.08, "14.5M"),
                MarketStock(4, "FCCL", "Fauji Cement Co", "Cement", 21.30, -1.45, -6.37, "8.7M"),
                MarketStock(5, "FFBL", "Fauji Fertilizer Bin Qasim", "Fertilizer", 32.10, -1.90, -5.59, "6.3M")
            )
            SymbolFilterType.VOLUME_SPIKES, SymbolFilterType.MOST_ACTIVE -> listOf(
                MarketStock(1, "WTL", "WorldCall Telecom", "Technology", 1.45, 0.12, 9.02, "42.1M"),
                MarketStock(2, "KEL", "K-Electric Limited", "Power Generation", 4.12, -0.38, -8.44, "35.2M"),
                MarketStock(3, "CNERGY", "Cnergyico PK Ltd", "Refinery", 4.88, 0.38, 8.44, "28.3M"),
                MarketStock(4, "BOP", "Bank of Punjab", "Commercial Banks", 8.42, 0.72, 9.35, "18.5M"),
                MarketStock(5, "SILK", "Silkbank Limited", "Commercial Banks", 1.05, -0.08, -7.08, "14.5M")
            )
            SymbolFilterType.WATCHLIST -> emptyList()
        }
    }

    private fun getFallbackSentiment(): MarketSentiment = MarketSentiment(
        overallScore = 68,
        sentimentLabel = "Bullish",
        positivePercent = 62,
        neutralPercent = 23,
        negativePercent = 15,
        newsCount = 48,
        aiSummary = "PSX market sentiment remains positive, driven by strong quarterly earnings in Commercial Banking and Oil & Gas exploration.",
        advanceDeclineRatio = 1.42,
        advancing = 195,
        declining = 137,
        unchanged = 42
    )

    private fun getFallbackSectors(): List<SectorPerformance> = listOf(
        SectorPerformance("sec_tech", "Technology & Comm.", 2.85, "48.2M", true),
        SectorPerformance("sec_energy", "Oil & Gas Exploration", 1.92, "32.1M", true),
        SectorPerformance("sec_bank", "Commercial Banks", 1.45, "64.8M", true),
        SectorPerformance("sec_cement", "Cement", -0.78, "21.4M", false),
        SectorPerformance("sec_chem", "Chemicals & Fert.", -1.15, "14.2M", false),
        SectorPerformance("sec_auto", "Automobile Assembler", 0.65, "8.9M", true)
    )
}
