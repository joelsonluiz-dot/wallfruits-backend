package com.wallfruits.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import javax.inject.Inject

@HiltViewModel
class OfferActionsViewModel @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {
    fun toggleFavorite(offerId: Long) {
        viewModelScope.launch {
            try {
                api.favoriteOffer(offerId.toString())
            } catch (_: Exception) {
            }
        }
    }

    fun toggleBookmark(offerId: Long) {
        viewModelScope.launch {
            try {
                api.bookmarkOffer(offerId.toString())
            } catch (_: Exception) {
            }
        }
    }

    fun reserve(offerId: Long, boxes: Int, pricePerBox: Double) {
        viewModelScope.launch {
            try {
                val body = buildJsonObject {
                    put("boxes", boxes)
                    put("price_per_box", pricePerBox)
                }
                api.reserveOffer(offerId.toString(), body)
            } catch (_: Exception) {
            }
        }
    }
}
