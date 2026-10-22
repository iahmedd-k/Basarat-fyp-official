package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.notifications.NotificationItemDto
import com.fyp.basarattradeinvest.data.remote.dto.notifications.NotificationsListResponseDto
import com.fyp.basarattradeinvest.domain.model.alerts.InAppNotification
import com.fyp.basarattradeinvest.domain.model.alerts.NotificationFeed

object NotificationDtoMapper {

    fun mapItemDtoToDomain(dto: NotificationItemDto): InAppNotification {
        return InAppNotification(
            id = dto.id,
            userId = dto.userId,
            ruleId = dto.ruleId,
            title = dto.title,
            message = dto.message,
            isRead = dto.isRead,
            createdAt = dto.createdAt
        )
    }

    fun mapListDtoToDomain(dto: NotificationsListResponseDto): NotificationFeed {
        return NotificationFeed(
            items = dto.notifications.map { mapItemDtoToDomain(it) },
            total = dto.total,
            page = dto.page,
            limit = dto.limit,
            hasMore = dto.hasMore
        )
    }
}
