package com.fyp.basarattradeinvest.feature.portfolio.main

import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioAllocation
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioOverview
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPerformance
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioPnL
import com.fyp.basarattradeinvest.domain.model.portfolio.PortfolioTransaction

sealed interface PortfolioMainUiState {
    data object Loading : PortfolioMainUiState
    data class Success(
        val overview: PortfolioOverview,
        val pnl: PortfolioPnL?,
        val allocation: PortfolioAllocation?,
        val performance: PortfolioPerformance?,
        val recentTransactions: List<PortfolioTransaction>,
        val isRefreshing: Boolean = false
    ) : PortfolioMainUiState
    data object Empty : PortfolioMainUiState
    data class Error(val message: String) : PortfolioMainUiState
}
