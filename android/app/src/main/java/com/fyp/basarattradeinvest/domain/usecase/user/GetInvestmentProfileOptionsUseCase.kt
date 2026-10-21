package com.fyp.basarattradeinvest.domain.usecase.user

import com.fyp.basarattradeinvest.domain.model.auth.InvestmentProfileOptions
import com.fyp.basarattradeinvest.domain.repository.UsersRepository

class GetInvestmentProfileOptionsUseCase(private val repository: UsersRepository) {
    suspend operator fun invoke(forceRefresh: Boolean = false): Result<InvestmentProfileOptions> {
        return repository.getInvestmentProfileOptions(forceRefresh)
    }
}
