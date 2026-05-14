package com.wallfruits.shared

import kotlinx.serialization.Serializable

@Serializable
data class Product(
    val id: String,
    val title: String,
    val priceCents: Long,
    val imageUrl: String? = null,
)
