package com.wallfruits.app

import kotlinx.serialization.Serializable

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
