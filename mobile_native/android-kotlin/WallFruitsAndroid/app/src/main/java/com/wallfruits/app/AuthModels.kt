package com.wallfruits.app

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class LoginRequest(
    val email: String,
    val password: String,
)

@Serializable
data class RegisterRequest(
    val name: String,
    val email: String,
    val password: String,
    val role: String,
)

@Serializable
data class CreateServiceRequest(
    val titulo: String,
    val descricao: String,
    val preco: String,
    val local: String,
    val imagem: String,
)

@Serializable
data class CreateBuyerClientRequest(
    val name: String,
    val company_name: String? = null,
    val city: String? = null,
    val state: String? = null,
    val management_scope: String = "joint",
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

@Serializable
data class CommunityPostsResponse(
    val posts: List<JsonObject> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class ServiceListResponse(
    val services: List<JsonObject> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class LibraryCatalogResponse(
    val items: List<JsonObject> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class BuyerClientsDashboardResponse(
    val clients: List<JsonObject> = emptyList(),
    val total: Int = 0,
)

@Serializable
data class NativeModulesSnapshot(
    val communityTotal: Int,
    val servicesTotal: Int,
    val managedServicesTotal: Int,
    val clientsTotal: Int,
    val libraryTotal: Int,
)

data class CommunityPreview(
    val id: String,
    val author: String,
    val text: String,
    val likes: Int,
    val comments: Int,
)

data class ServicePreview(
    val id: String,
    val title: String,
    val description: String,
    val price: String,
    val location: String,
)

data class BuyerClientPreview(
    val id: String,
    val name: String,
    val company: String,
    val cityState: String,
    val managementScope: String,
)

data class LibraryPreview(
    val id: String,
    val title: String,
    val author: String,
    val category: String,
    val readTime: String,
)
