package com.wallfruits.app

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface AuthApi {
    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("api/auth/me")
    suspend fun me(): ApiUser

    @GET("api/offers")
    suspend fun offers(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 5,
    ): OffersResponse

    @GET("api/store/orders/my")
    suspend fun myOrders(): StoreOrdersResponse

    @GET("api/ai/agenda/market-intelligence")
    suspend fun marketIntelligence(): AIMarketSnapshot
}
