package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.mapper.NotificationDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.NotificationsApiService
import com.fyp.basarattradeinvest.domain.model.alerts.NotificationFeed
import com.fyp.basarattradeinvest.domain.repository.NotificationsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class NotificationsRepositoryImpl(
    private val apiService: NotificationsApiService = NetworkClient.notificationsApiService
) : NotificationsRepository {

    override suspend fun getNotifications(
        page: Int?,
        limit: Int?,
        unreadOnly: Boolean?
    ): Result<NotificationFeed> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getNotifications(
                page = page,
                limit = limit,
                unreadOnly = unreadOnly
            )
            if (response.isSuccessful && response.body() != null) {
                val domain = NotificationDtoMapper.mapListDtoToDomain(response.body()!!)
                Result.success(domain)
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun markNotificationAsRead(notificationId: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.markNotificationAsRead(notificationId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
