package com.wallfruits.app

import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

@Singleton
class AuthRepository @Inject constructor(
    private val api: AuthApi,
    private val sessionStore: SessionStore,
) {
    suspend fun register(name: String, email: String, password: String, role: String): ApiUser {
        return api.register(
            RegisterRequest(
                name = name.trim(),
                email = email.trim(),
                password = password,
                role = role,
            )
        )
    }

    suspend fun login(email: String, password: String): ApiUser {
        val response = api.login(LoginRequest(email = email.trim(), password = password))
        sessionStore.accessToken = response.access_token
        sessionStore.userName = response.user.name
        return response.user
    }

    fun currentUserName(): String? = sessionStore.userName

    fun currentToken(): String? = sessionStore.accessToken

    suspend fun loadDashboardSnapshot(): DashboardSnapshot {
        val offers = api.offers(limit = 5)
        val orders = api.myOrders()
        val ai = api.marketIntelligence()

        val aiSignals = ai.alerts.size + ai.recommendations.size + ai.opportunities.size
        return DashboardSnapshot(
            offersTotal = offers.total,
            ordersTotal = orders.total,
            aiSignals = aiSignals,
        )
    }

    suspend fun loadNativeModulesSnapshot(): NativeModulesSnapshot {
        suspend fun safeCount(block: suspend () -> Int): Int = runCatching { block() }.getOrDefault(0)

        return NativeModulesSnapshot(
            communityTotal = safeCount { api.communityPosts(limit = 1).total },
            servicesTotal = safeCount { api.services(limit = 1).total },
            managedServicesTotal = safeCount { api.managedServices(limit = 1).total },
            clientsTotal = safeCount { api.buyerClientsDashboard().total },
            libraryTotal = safeCount { api.libraryCatalog().total },
        )
    }

    suspend fun loadCommunityPreview(limit: Int = 12): List<CommunityPreview> {
        val response = api.communityPosts(limit = limit)
        return response.posts.mapIndexed { index, item ->
            CommunityPreview(
                id = item.stringValue("id", "post_id") ?: "post-$index",
                author = item.stringValue("author_name", "author", "user_name") ?: "Comunidade WallFruits",
                text = item.stringValue("content", "text", "caption", "title") ?: "Post sem descricao",
                likes = item.intValue("likes_count", "likes") ?: 0,
                comments = item.intValue("comments_count", "comments") ?: 0,
            )
        }
    }

    suspend fun loadServicesPreview(limit: Int = 20): List<ServicePreview> {
        val response = api.services(limit = limit)
        return response.services.mapIndexed { index, item ->
            ServicePreview(
                id = item.stringValue("id", "service_id") ?: "service-$index",
                title = item.stringValue("titulo", "title", "name") ?: "Servico",
                description = item.stringValue("descricao", "description", "summary") ?: "Sem descricao",
                price = item.stringValue("preco", "price", "valor") ?: "A combinar",
                location = item.stringValue("local", "location", "cidade") ?: "Local nao informado",
            )
        }
    }

    suspend fun loadManagedServicesPreview(limit: Int = 20): List<ServicePreview> {
        val response = api.managedServices(limit = limit)
        return response.services.mapIndexed { index, item ->
            ServicePreview(
                id = item.stringValue("id", "service_id") ?: "managed-service-$index",
                title = item.stringValue("titulo", "title", "name") ?: "Servico",
                description = item.stringValue("descricao", "description", "summary") ?: "Sem descricao",
                price = item.stringValue("preco", "price", "valor") ?: "A combinar",
                location = item.stringValue("local", "location", "cidade") ?: "Local nao informado",
            )
        }
    }

    suspend fun loadBuyerClientsPreview(): List<BuyerClientPreview> {
        val response = api.buyerClientsDashboard()
        return response.clients.mapIndexed { index, item ->
            val city = item.stringValue("city")
            val state = item.stringValue("state")
            BuyerClientPreview(
                id = item.stringValue("id", "client_id") ?: "client-$index",
                name = item.stringValue("name") ?: "Cliente",
                company = item.stringValue("company_name") ?: "Sem empresa",
                cityState = listOfNotNull(city, state).joinToString("/").ifBlank { "Nao informado" },
                managementScope = item.stringValue("management_scope") ?: "joint",
            )
        }
    }

    suspend fun loadLibraryPreview(limit: Int = 24): List<LibraryPreview> {
        val response = api.libraryCatalog()
        return response.items.take(limit).mapIndexed { index, item ->
            LibraryPreview(
                id = item.stringValue("id", "book_id") ?: "book-$index",
                title = item.stringValue("title", "name") ?: "Leitura",
                author = item.stringValue("author") ?: "Autor nao informado",
                category = item.stringValue("category") ?: "Sem categoria",
                readTime = item.stringValue("read_time") ?: "Tempo livre",
            )
        }
    }

    fun logout() = sessionStore.clear()
}

private fun JsonObject.stringValue(vararg keys: String): String? {
    keys.forEach { key ->
        val primitive = this[key] as? JsonPrimitive ?: return@forEach
        primitive.contentOrNull?.trim()?.takeIf { it.isNotEmpty() }?.let { return it }
    }
    return null
}

private fun JsonObject.intValue(vararg keys: String): Int? {
    keys.forEach { key ->
        val primitive = this[key] as? JsonPrimitive ?: return@forEach
        primitive.intOrNull?.let { return it }
        primitive.contentOrNull?.toIntOrNull()?.let { return it }
    }
    return null
}
