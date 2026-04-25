package com.wallfruits.app

import javax.inject.Inject
import javax.inject.Singleton

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

    fun logout() = sessionStore.clear()
}
