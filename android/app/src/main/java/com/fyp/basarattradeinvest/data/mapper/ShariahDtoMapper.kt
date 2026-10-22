package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.shariah.Kmi30ConstituentDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahCriteriaResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahCriterionDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahKmi30ResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahPurificationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.shariah.ShariahScreeningResponseDto
import com.fyp.basarattradeinvest.domain.model.shariah.ShariahStock
import com.fyp.basarattradeinvest.domain.model.shariah.DividendPurificationResult
import com.fyp.basarattradeinvest.domain.model.shariah.Kmi30Constituent
import com.fyp.basarattradeinvest.domain.model.shariah.Kmi30IndexSummary
import com.fyp.basarattradeinvest.domain.model.shariah.ShariahCriterionItem
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCompliance
import com.fyp.basarattradeinvest.domain.model.shariah.StockShariahCriteria

object ShariahDtoMapper {

    fun mapKmi30Response(dto: ShariahKmi30ResponseDto): Kmi30IndexSummary {
        val list = dto.constituents.map { mapConstituent(it) }
        return Kmi30IndexSummary(
            index = dto.index,
            totalConstituents = dto.totalConstituents ?: list.size,
            asOf = dto.asOf,
            isStale = dto.isStale,
            constituents = list
        )
    }

    fun mapConstituent(dto: Kmi30ConstituentDto): Kmi30Constituent {
        return Kmi30Constituent(
            symbol = dto.symbol,
            name = dto.name ?: dto.symbol,
            isCompliant = dto.isShariahCompliant,
            debtRatio = dto.debtRatio,
            interestIncomeRatio = dto.interestIncomeRatio,
            dataAsOf = dto.dataAsOf,
            purificationRateProvisional = dto.purificationRateProvisional
        )
    }

    fun mapConstituentToLegacyStock(item: Kmi30Constituent): ShariahStock {
        return ShariahStock(
            symbol = item.symbol,
            companyName = item.name,
            purificationRate = item.interestIncomeRatio,
            purificationProvisional = item.purificationRateProvisional,
            isCompliant = item.isCompliant,
            isKmi30 = true
        )
    }

    fun mapScreeningResponse(dto: ShariahScreeningResponseDto): StockShariahCompliance {
        return StockShariahCompliance(
            symbol = dto.symbol,
            screeningAvailable = dto.screeningAvailable,
            isCompliant = dto.isShariahCompliant,
            overallScore = dto.overallScore,
            screeningMethod = dto.screeningMethod,
            screenedAt = dto.screenedAt,
            dataAsOf = dto.dataAsOf,
            dataIsStale = dto.dataIsStale,
            sector = dto.sector,
            purificationRate = dto.purificationRate,
            purificationRateProvisional = dto.purificationRateProvisional,
            complianceSummary = dto.complianceSummary
        )
    }

    fun mapCriteriaResponse(dto: ShariahCriteriaResponseDto): StockShariahCriteria {
        return StockShariahCriteria(
            symbol = dto.symbol,
            screeningAvailable = dto.screeningAvailable,
            isCompliant = dto.isShariahCompliant,
            criteria = dto.criteria.map { mapCriterion(it) }
        )
    }

    fun mapCriterion(dto: ShariahCriterionDto): ShariahCriterionItem {
        return ShariahCriterionItem(
            name = dto.name,
            threshold = dto.threshold,
            value = dto.value,
            passed = dto.passed,
            description = dto.description,
            exception = dto.exception
        )
    }

    fun mapPurificationResponse(dto: ShariahPurificationResponseDto): DividendPurificationResult {
        return DividendPurificationResult(
            symbol = dto.symbol,
            dividendIncome = dto.dividendIncome,
            purificationAmount = dto.purificationAmount,
            purificationRate = dto.purificationRate,
            notes = dto.notes,
            rateIsProvisional = dto.rateIsProvisional
        )
    }
}
