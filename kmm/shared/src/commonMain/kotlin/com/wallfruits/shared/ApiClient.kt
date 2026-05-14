package com.wallfruits.shared

import io.ktor.client.*
import io.ktor.client.call.*
import io.ktor.client.request.*
import io.ktor.client.statement.*
import io.ktor.client.plugins.contentnegotiation.*
import io.ktor.serialization.kotlinx.json.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json

/**
 * Minimal shared API client using Ktor.
 * Platform modules should provide a proper HttpClient engine configuration.
 */
class ApiClient(private val client: HttpClient, private val baseUrl: String) {
    suspend fun fetchProducts(): List<Product> = withContext(Dispatchers.Default) {
        val resp: HttpResponse = client.get("${'$'}baseUrl/api/store/products")
        if (resp.status.value in 200..299) {
            resp.body()
        } else {
            emptyList()
        }
    }
}

object ApiClientFactory {
    fun create(baseUrl: String = "https://wallfruits-backend.onrender.com"): ApiClient {
        val client = HttpClient {
            install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
        }
        return ApiClient(client, baseUrl)
    }
}
