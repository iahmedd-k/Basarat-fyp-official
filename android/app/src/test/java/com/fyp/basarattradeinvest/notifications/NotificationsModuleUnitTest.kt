package com.fyp.basarattradeinvest.notifications

import com.fyp.basarattradeinvest.data.mapper.NotificationDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.NotificationsApiService
import com.fyp.basarattradeinvest.data.remote.dto.notifications.NotificationItemDto
import com.fyp.basarattradeinvest.data.remote.dto.notifications.NotificationsListResponseDto
import com.fyp.basarattradeinvest.data.repository.NotificationsRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.notifications.GetNotificationsUseCase
import com.fyp.basarattradeinvest.domain.usecase.notifications.MarkNotificationReadUseCase
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Response

class NotificationsModuleUnitTest {

    private class FakeNotificationsApiService : NotificationsApiService {
        var shouldFail: Boolean = false
        val storedNotifications = mutableListOf<NotificationItemDto>()

        override suspend fun getNotifications(
            page: Int?,
            limit: Int?,
            unreadOnly: Boolean?
        ): Response<NotificationsListResponseDto> {
            if (shouldFail) {
                return Response.error(500, "{\"detail\":\"Internal server error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            val filtered = if (unreadOnly == true) {
                storedNotifications.filter { !it.isRead }
            } else {
                storedNotifications.toList()
            }
            val responseDto = NotificationsListResponseDto(
                notifications = filtered,
                total = filtered.size,
                page = page ?: 1,
                limit = limit ?: 20,
                hasMore = false
            )
            return Response.success(responseDto)
        }

        override suspend fun markNotificationAsRead(notificationId: String): Response<Unit> {
            if (shouldFail) {
                return Response.error(404, "{\"detail\":\"Notification not found\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            val index = storedNotifications.indexOfFirst { it.id == notificationId }
            if (index != -1) {
                storedNotifications[index] = storedNotifications[index].copy(isRead = true)
            }
            return Response.success(204, Unit)
        }
    }

    private lateinit var fakeApiService: FakeNotificationsApiService
    private lateinit var repository: NotificationsRepositoryImpl
    private lateinit var getNotificationsUseCase: GetNotificationsUseCase
    private lateinit var markNotificationReadUseCase: MarkNotificationReadUseCase

    @Before
    fun setUp() {
        fakeApiService = FakeNotificationsApiService()
        repository = NotificationsRepositoryImpl(fakeApiService)
        getNotificationsUseCase = GetNotificationsUseCase(repository)
        markNotificationReadUseCase = MarkNotificationReadUseCase(repository)
    }

    @Test
    fun testNotificationDtoMapper_mapItemDtoToDomain() {
        val dto = NotificationItemDto(
            id = "notif-1",
            userId = "user-100",
            ruleId = "rule-5",
            title = "KSE-100 Surpassed 85,000",
            message = "Market gained +550 points in high volume trading.",
            isRead = false,
            createdAt = "2026-09-24T10:00:00Z"
        )
        val domain = NotificationDtoMapper.mapItemDtoToDomain(dto)

        assertEquals("notif-1", domain.id)
        assertEquals("user-100", domain.userId)
        assertEquals("rule-5", domain.ruleId)
        assertEquals("KSE-100 Surpassed 85,000", domain.title)
        assertEquals("Market gained +550 points in high volume trading.", domain.message)
        assertFalse(domain.isRead)
        assertNotNull(domain.formattedTime)
    }

    @Test
    fun testNotificationDtoMapper_mapListDtoToDomain() {
        val dtoList = listOf(
            NotificationItemDto(
                id = "notif-1",
                userId = "user-100",
                ruleId = null,
                title = "Alert Triggered",
                message = "LUCK crossed PKR 125.00",
                isRead = false,
                createdAt = "2026-09-24T10:00:00Z"
            ),
            NotificationItemDto(
                id = "notif-2",
                userId = "user-100",
                ruleId = null,
                title = "System Notice",
                message = "Market hours updated",
                isRead = true,
                createdAt = "2026-09-24T09:00:00Z"
            )
        )
        val responseDto = NotificationsListResponseDto(
            notifications = dtoList,
            total = 2,
            page = 1,
            limit = 20,
            hasMore = false
        )
        val feed = NotificationDtoMapper.mapListDtoToDomain(responseDto)

        assertEquals(2, feed.items.size)
        assertEquals(2, feed.total)
        assertEquals(1, feed.page)
        assertFalse(feed.hasMore)
        assertEquals(1, feed.unreadCount)
    }

    @Test
    fun testRepository_GetNotifications_Lifecycle() = runBlocking {
        fakeApiService.storedNotifications.addAll(
            listOf(
                NotificationItemDto(
                    id = "n-1",
                    userId = "user-1",
                    ruleId = "r-1",
                    title = "Target Hit",
                    message = "OGDC rose above 110",
                    isRead = false,
                    createdAt = "2026-09-24T10:00:00Z"
                ),
                NotificationItemDto(
                    id = "n-2",
                    userId = "user-1",
                    ruleId = null,
                    title = "Dividend Announced",
                    message = "ENGRO announced dividend",
                    isRead = true,
                    createdAt = "2026-09-24T08:00:00Z"
                )
            )
        )

        // 1. Fetch All
        val allResult = repository.getNotifications(page = 1, limit = 20, unreadOnly = null)
        assertTrue(allResult.isSuccess)
        val allFeed = allResult.getOrNull()!!
        assertEquals(2, allFeed.items.size)

        // 2. Fetch Unread Only
        val unreadResult = repository.getNotifications(page = 1, limit = 20, unreadOnly = true)
        assertTrue(unreadResult.isSuccess)
        val unreadFeed = unreadResult.getOrNull()!!
        assertEquals(1, unreadFeed.items.size)
        assertEquals("n-1", unreadFeed.items[0].id)

        // 3. Mark as Read
        val markResult = repository.markNotificationAsRead("n-1")
        assertTrue(markResult.isSuccess)

        // 4. Fetch Unread Only again -> should be empty
        val unreadAfterMark = repository.getNotifications(page = 1, limit = 20, unreadOnly = true)
        assertTrue(unreadAfterMark.isSuccess)
        assertTrue(unreadAfterMark.getOrNull()!!.items.isEmpty())
    }

    @Test
    fun testUseCases_Execution() = runBlocking {
        fakeApiService.storedNotifications.add(
            NotificationItemDto(
                id = "n-test",
                userId = "u-test",
                ruleId = null,
                title = "Test Notification",
                message = "Testing use cases",
                isRead = false,
                createdAt = "2026-09-24T10:00:00Z"
            )
        )

        val feed = getNotificationsUseCase(page = 1, limit = 10, unreadOnly = false).getOrNull()
        assertNotNull(feed)
        assertEquals(1, feed?.items?.size)

        val markRes = markNotificationReadUseCase("n-test")
        assertTrue(markRes.isSuccess)

        val updatedFeed = getNotificationsUseCase(page = 1, limit = 10, unreadOnly = false).getOrNull()
        assertTrue(updatedFeed?.items?.first()?.isRead == true)
    }
}
