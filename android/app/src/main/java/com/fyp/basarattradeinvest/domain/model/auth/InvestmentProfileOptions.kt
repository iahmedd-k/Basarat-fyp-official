package com.fyp.basarattradeinvest.domain.model.auth

data class InvestmentProfileOptions(
    val riskTolerances: List<String>,
    val investmentHorizons: List<String>,
    val sectors: List<String>,
    val noPreference: String,
    val description: String?
)
