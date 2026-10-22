package com.fyp.basarattradeinvest.feature.portfolio.main

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.core.session.AuthState
import com.fyp.basarattradeinvest.core.session.SessionManager
import com.fyp.basarattradeinvest.data.repository.PortfolioRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPerformance
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPnL
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction
import com.fyp.basarattradeinvest.domain.repository.PortfolioRepository
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetPortfolioAllocationUseCase
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetPortfolioOverviewUseCase
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetPortfolioPerformanceUseCase
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetPortfolioPnLUseCase
import com.fyp.basarattradeinvest.domain.usecase.portfolio.GetTransactionsUseCase
import kotlinx.coroutines.async
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class PortfolioMainViewModel(
    private val getOverviewUseCase: GetPortfolioOverviewUseCase,
    private val getPnLUseCase: GetPortfolioPnLUseCase,
    private val getAllocationUseCase: GetPortfolioAllocationUseCase,
    private val getPerformanceUseCase: GetPortfolioPerformanceUseCase,
    private val getTransactionsUseCase: GetTransactionsUseCase
) : ViewModel() {

    constructor() : this(PortfolioRepositoryImpl())

    constructor(repository: PortfolioRepository) : this(
        getOverviewUseCase = GetPortfolioOverviewUseCase(repository),
        getPnLUseCase = GetPortfolioPnLUseCase(repository),
        getAllocationUseCase = GetPortfolioAllocationUseCase(repository),
        getPerformanceUseCase = GetPortfolioPerformanceUseCase(repository),
        getTransactionsUseCase = GetTransactionsUseCase(repository)
    )

    class Factory(
        private val repository: PortfolioRepository = PortfolioRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(PortfolioMainViewModel::class.java)) {
                return PortfolioMainViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }

    private val _uiState = MutableStateFlow<PortfolioMainUiState>(PortfolioMainUiState.Loading)
    val uiState: StateFlow<PortfolioMainUiState> = _uiState.asStateFlow()

    private val _selectedPeriod = MutableStateFlow("1M")
    val selectedPeriod: StateFlow<String> = _selectedPeriod.asStateFlow()

    private val _selectedTab = MutableStateFlow(0) // 0: Holdings, 1: PnL, 2: Allocation, 3: Performance, 4: History
    val selectedTab: StateFlow<Int> = _selectedTab.asStateFlow()
    private var lastSuccessfulFetchAt: Long = 0L
    private val freshnessWindowMs = 5 * 60 * 1000L
    private var isPortfolioLoading = false
    private var pendingForcedRefresh = false
    private var accountGeneration = 0
    private var currentAccountKey: String? = accountKeyForCurrentSession()
    private var portfolioLoadJob: Job? = null

    init {
        viewModelScope.launch {
            SessionManager.authState.collect { authState ->
                val nextAccountKey = accountKeyFor(authState)
                if (nextAccountKey == currentAccountKey) return@collect

                currentAccountKey = nextAccountKey
                accountGeneration++
                portfolioLoadJob?.cancel()
                portfolioLoadJob = null
                isPortfolioLoading = false
                pendingForcedRefresh = false
                lastSuccessfulFetchAt = 0L
                _uiState.value = PortfolioMainUiState.Loading

                if (nextAccountKey != null) {
                    loadPortfolio(forceRefresh = true)
                }
            }
        }
    }

    fun ensureLoaded() {
        val state = _uiState.value
        val shouldLoad = state !is PortfolioMainUiState.Success || stateHasExpired()
        if (shouldLoad) {
            loadPortfolio(forceRefresh = false)
        }
    }

    private fun stateHasExpired(): Boolean {
        return System.currentTimeMillis() - lastSuccessfulFetchAt > freshnessWindowMs
    }

    fun selectTab(tabIndex: Int) {
        _selectedTab.value = tabIndex
    }

    fun setPeriod(period: String) {
        if (_selectedPeriod.value == period) return
        _selectedPeriod.value = period
        if (currentAccountKey == null) return
        viewModelScope.launch {
            val perfResult = getPerformanceUseCase(period)
            val currentState = _uiState.value
            if (currentState is PortfolioMainUiState.Success && perfResult.isSuccess) {
                _uiState.value = currentState.copy(performance = perfResult.getOrNull())
            }
        }
    }

    fun loadPortfolio(forceRefresh: Boolean = false) {
        if (currentAccountKey == null) {
            _uiState.value = PortfolioMainUiState.Loading
            return
        }
        if (isPortfolioLoading) {
            if (forceRefresh) {
                pendingForcedRefresh = true
                (_uiState.value as? PortfolioMainUiState.Success)?.let {
                    _uiState.value = it.copy(isRefreshing = true)
                }
            }
            return
        }

        val currentState = _uiState.value
        val hasUsableData = currentState is PortfolioMainUiState.Success
        val shouldSkip = !forceRefresh && hasUsableData && !stateHasExpired()
        if (shouldSkip) return

        isPortfolioLoading = true
        if (forceRefresh) {
            (_uiState.value as? PortfolioMainUiState.Success)?.let {
                _uiState.value = it.copy(isRefreshing = true)
            }
        }
        val loadGeneration = accountGeneration
        portfolioLoadJob = viewModelScope.launch {
            try {
                if (!forceRefresh && !hasUsableData) {
                    _uiState.value = PortfolioMainUiState.Loading
                }

                coroutineScope {
                    val overviewDeferred = async { getOverviewUseCase() }
                    val pnlDeferred = async { getPnLUseCase() }
                    val allocationDeferred = async { getAllocationUseCase() }
                    val performanceDeferred = async { getPerformanceUseCase(_selectedPeriod.value) }
                    val transactionsDeferred = async { getTransactionsUseCase(page = 1, limit = 5) }

                    val overviewRes = overviewDeferred.await()
                    if (loadGeneration != accountGeneration) return@coroutineScope
                    val overview = overviewRes.getOrNull()
                    if (overview == null) {
                        val error = overviewRes.exceptionOrNull()?.message ?: "Unable to load portfolio overview."
                        if (_uiState.value !is PortfolioMainUiState.Success) {
                            _uiState.value = PortfolioMainUiState.Error(error)
                        }
                        pnlDeferred.cancel()
                        allocationDeferred.cancel()
                        performanceDeferred.cancel()
                        transactionsDeferred.cancel()
                        return@coroutineScope
                    }

                    if (overview.holdings.isEmpty() && overview.summary.totalInvested == 0.0) {
                        _uiState.value = PortfolioMainUiState.Empty
                        pnlDeferred.cancel()
                        allocationDeferred.cancel()
                        performanceDeferred.cancel()
                        transactionsDeferred.cancel()
                        return@coroutineScope
                    }

                    val existing = _uiState.value as? PortfolioMainUiState.Success
                    _uiState.value = PortfolioMainUiState.Success(
                        overview = overview,
                        pnl = existing?.pnl,
                        allocation = existing?.allocation,
                        performance = existing?.performance,
                        recentTransactions = existing?.recentTransactions.orEmpty(),
                        isRefreshing = forceRefresh || existing?.isRefreshing == true
                    )

                    launch {
                        val result = pnlDeferred.await()
                        updateSuccessState(loadGeneration) { copy(pnl = result.getOrNull()) }
                    }

                    launch {
                        val result = allocationDeferred.await()
                        updateSuccessState(loadGeneration) { copy(allocation = result.getOrNull()) }
                    }

                    launch {
                        val result = performanceDeferred.await()
                        updateSuccessState(loadGeneration) { copy(performance = result.getOrNull()) }
                    }

                    launch {
                        val result = transactionsDeferred.await()
                        updateSuccessState(loadGeneration) {
                            copy(recentTransactions = result.getOrNull()?.items ?: emptyList())
                        }
                    }
                }
                if (loadGeneration == accountGeneration) {
                    lastSuccessfulFetchAt = System.currentTimeMillis()
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (e: Exception) {
                if (loadGeneration == accountGeneration && _uiState.value !is PortfolioMainUiState.Success) {
                    _uiState.value = PortfolioMainUiState.Error(e.localizedMessage ?: "Unexpected error occurred.")
                }
            } finally {
                if (loadGeneration == accountGeneration) {
                    isPortfolioLoading = false
                    portfolioLoadJob = null
                    (_uiState.value as? PortfolioMainUiState.Success)?.let {
                        _uiState.value = it.copy(isRefreshing = false)
                    }
                    if (pendingForcedRefresh) {
                        pendingForcedRefresh = false
                        loadPortfolio(forceRefresh = true)
                    }
                }
            }
        }
    }

    private fun updateSuccessState(
        generation: Int,
        update: PortfolioMainUiState.Success.() -> PortfolioMainUiState.Success
    ) {
        if (generation != accountGeneration) return
        val current = _uiState.value as? PortfolioMainUiState.Success ?: return
        _uiState.value = current.update()
    }

    private fun accountKeyForCurrentSession(): String? = accountKeyFor(SessionManager.authState.value)

    private fun accountKeyFor(authState: AuthState): String? = (authState as? AuthState.Authenticated)
        ?.let {
            SessionManager.getCurrentUserId()?.takeIf(String::isNotBlank)
                ?: it.userEmail.takeIf(String::isNotBlank)
        }
        ?.lowercase()
}
