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
class OfferActionsViewModelV2 @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {

    fun toggleFavorite(offerId: Long, snackbar: SnackbarViewModel) {
        viewModelScope.launch {
            try {
                api.favoriteOffer(offerId.toString())
                snackbar.showMessage("Oferta curtida!", SnackbarType.SUCCESS)
            } catch (e: Exception) {
                snackbar.showMessage("Erro ao curtir oferta.", SnackbarType.ERROR)
            }
        }
    }

    fun toggleBookmark(offerId: Long, snackbar: SnackbarViewModel) {
        viewModelScope.launch {
            try {
                api.bookmarkOffer(offerId.toString())
                snackbar.showMessage("Oferta salva!", SnackbarType.SUCCESS)
            } catch (e: Exception) {
                snackbar.showMessage("Erro ao salvar oferta.", SnackbarType.ERROR)
            }
        }
    }

    fun reserve(offerId: Long, boxes: Int, pricePerBox: Double, snackbar: SnackbarViewModel) {
        viewModelScope.launch {
            try {
                val body = buildJsonObject {
                    put("boxes", boxes)
                    put("price_per_box", pricePerBox)
                }
                api.reserveOffer(offerId.toString(), body)
                snackbar.showMessage("Reserva confirmada!", SnackbarType.SUCCESS)
            } catch (e: Exception) {
                snackbar.showMessage("Erro ao reservar oferta.", SnackbarType.ERROR)
            }
        }
    }
}
