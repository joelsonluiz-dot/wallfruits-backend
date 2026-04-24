package com.wallfruits.app

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class LoginRequest(
    val email: String,
    val password: String,
)

@Serializable
data class ApiUser(
    val id: Int,
    val name: String,
    val email: String,
    val role: String,
    val platform_role: String? = null,
    val account_role: String? = null,
    val account_scope_id: String? = null,
    val profile_image: String? = null,
)

@Serializable
data class LoginResponse(
    val access_token: String,
    val token_type: String,
    val user: ApiUser,
)

@Serializable
data class OfferItem(
    val id: String,
    val product_name: String,
)

@Serializable
data class OffersResponse(
    val total: Int,
    val skip: Int,
    val limit: Int,
    val offers: List<OfferItem>,
)

@Serializable
data class StoreOrderItem(
    val id: Int,
    val status: String,
)

@Serializable
data class StoreOrdersResponse(
    val orders: List<StoreOrderItem>,
    val total: Int,
)

@Serializable
data class DashboardSnapshot(
    val offersTotal: Int,
    val ordersTotal: Int,
    val aiSignals: Int,
)

@Serializable
data class AIMarketSnapshot(
    val alerts: List<JsonObject> = emptyList(),
    val recommendations: List<JsonObject> = emptyList(),
    val opportunities: List<JsonObject> = emptyList(),
)
