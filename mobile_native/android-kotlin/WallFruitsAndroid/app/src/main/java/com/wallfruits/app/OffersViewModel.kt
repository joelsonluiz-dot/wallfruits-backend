package com.wallfruits.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class OffersViewModel @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {
    private val _offers = MutableStateFlow<List<OfferItem>>(emptyList())
    val offers = _offers.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            try {
                val resp = api.offers(skip = 0, limit = 20)
                _offers.value = resp.offers.map {
                    OfferItem(it.id, it.product_name ?: "Produto", it.price ?: 0.0)
                }
            } catch (e: Exception) {
                // keep empty on failure
            }
        }
    }
}

data class OfferItem(val id: Long, val title: String, val price: Double)
