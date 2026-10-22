package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.watchlist.WatchlistCheckResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.watchlist.WatchlistDetailResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.watchlist.WatchlistItemCreateRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.watchlist.WatchlistItemResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface WatchlistApiService {
    @GET("api/v1/watchlists/default")
    suspend fun getDefaultWatchlist(): Response<WatchlistDetailResponseDto>

    @GET("api/v1/watchlists/check/{symbol}")
    suspend fun checkSymbol(@Path("symbol") symbol: String): Response<WatchlistCheckResponseDto>

    @POST("api/v1/watchlists/{watchlist_id}/items")
    suspend fun addItem(
        @Path("watchlist_id") watchlistId: String,
        @Body request: WatchlistItemCreateRequestDto
    ): Response<WatchlistItemResponseDto>

    @DELETE("api/v1/watchlists/{watchlist_id}/items/{symbol_or_item_id}")
    suspend fun removeItem(
        @Path("watchlist_id") watchlistId: String,
        @Path("symbol_or_item_id") symbolOrItemId: String
    ): Response<Unit>
}
