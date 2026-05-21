package com.wallfruits.app

import kotlinx.serialization.json.JsonObject
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.Path
import retrofit2.http.POST
import retrofit2.http.Query

interface AuthApi {
    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @POST("api/auth/register")
    suspend fun register(@Body request: RegisterRequest): ApiUser

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

    @GET("api/community/posts")
    suspend fun communityPosts(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 1,
    ): CommunityPostsResponse

    @GET("api/services")
    suspend fun services(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 1,
    ): ServiceListResponse

    @GET("api/services/manage/list")
    suspend fun managedServices(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 1,
    ): ServiceListResponse

    @GET("api/library/catalog")
    suspend fun libraryCatalog(): LibraryCatalogResponse

    @GET("social/users/{userId}")
    suspend fun publicProfile(
        @Path("userId") userId: String,
    ): JsonObject

    @GET("api/buyer-clients/dashboard")
    suspend fun buyerClientsDashboard(): BuyerClientsDashboardResponse

    @POST("api/services")
    suspend fun createService(@Body request: CreateServiceRequest): JsonObject

    @PATCH("api/services/{serviceId}")
    suspend fun updateService(
        @Path("serviceId") serviceId: String,
        @Body request: UpdateServiceRequest,
    ): JsonObject

    @DELETE("api/services/{serviceId}")
    suspend fun deleteService(@Path("serviceId") serviceId: String): JsonObject

    @POST("api/buyer-clients")
    suspend fun createBuyerClient(@Body request: CreateBuyerClientRequest): JsonObject

    @PATCH("api/buyer-clients/{clientId}")
    suspend fun updateBuyerClient(
        @Path("clientId") clientId: String,
        @Body request: UpdateBuyerClientRequest,
    ): JsonObject

    @DELETE("api/buyer-clients/{clientId}")
    suspend fun deleteBuyerClient(@Path("clientId") clientId: String): JsonObject
}
