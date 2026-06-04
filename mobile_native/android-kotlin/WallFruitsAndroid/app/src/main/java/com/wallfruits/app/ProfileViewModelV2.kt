package com.wallfruits.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import javax.inject.Inject

@HiltViewModel
class ProfileViewModelV2 @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {
    private val _profile = MutableStateFlow<JsonObject?>(null)
    val profile = _profile.asStateFlow()

    private val _isFollowing = MutableStateFlow(false)
    val isFollowing = _isFollowing.asStateFlow()

    fun load(userId: String) {
        viewModelScope.launch {
            try {
                val resp = api.publicProfile(userId)
                _profile.value = resp
                // check if following status is in payload
                if (resp["is_following"]?.toString() == "true") {
                    _isFollowing.value = true
                }
            } catch (_: Exception) {
            }
        }
    }

    fun toggleFollow(userId: String, snackbar: SnackbarViewModel) {
        viewModelScope.launch {
            try {
                api.followUser(userId)
                _isFollowing.value = !_isFollowing.value
                val msg = if (_isFollowing.value) "Você seguiu o usuário!" else "Você deixou de seguir."
                snackbar.showMessage(msg, SnackbarType.SUCCESS)
            } catch (e: Exception) {
                snackbar.showMessage("Erro ao seguir usuário.", SnackbarType.ERROR)
            }
        }
    }

    fun sendMessage(userId: String, body: String, snackbar: SnackbarViewModel) {
        viewModelScope.launch {
            try {
                val payload = buildJsonObject {
                    put("to_user_id", userId.toLong())
                    put("body", body)
                }
                api.sendMessage(payload)
                snackbar.showMessage("Mensagem enviada!", SnackbarType.SUCCESS)
            } catch (e: Exception) {
                snackbar.showMessage("Erro ao enviar mensagem.", SnackbarType.ERROR)
            }
        }
    }
}
