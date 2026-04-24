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

    fun logout() = sessionStore.clear()
}
