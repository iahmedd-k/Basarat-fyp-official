package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.alerts.AlertResponseDto
import com.fyp.basarattradeinvest.domain.model.alerts.AlertItem

object AlertDtoMapper {

    fun mapAlertDtoToDomain(dto: AlertResponseDto): AlertItem {
        return AlertItem(
            id = dto.id,
            userId = dto.userId,
            ruleId = dto.ruleId,
            title = dto.title,
            message = dto.message,
            isRead = dto.isRead,
            createdAt = dto.createdAt
        )
    }
}
