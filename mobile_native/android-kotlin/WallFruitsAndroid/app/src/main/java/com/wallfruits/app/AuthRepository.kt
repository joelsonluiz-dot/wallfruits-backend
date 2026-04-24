package com.wallfruits.app

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: AuthApi,
    private val sessionStore: SessionStore,
) {
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

    fun logout() = sessionStore.clear()
}
