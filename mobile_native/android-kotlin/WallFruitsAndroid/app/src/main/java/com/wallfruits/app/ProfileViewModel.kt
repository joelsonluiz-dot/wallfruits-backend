package com.wallfruits.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import javax.inject.Inject

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {
    private val _profile = MutableStateFlow<JsonObject?>(null)
    val profile = _profile.asStateFlow()

    fun load(userId: String) {
        viewModelScope.launch {
            try {
                val resp = api.publicProfile(userId)
                _profile.value = resp
            } catch (_: Exception) {
                // ignore
            }
        }
    }

    fun toggleFollow(userId: String) {
        viewModelScope.launch {
            try {
                api.followUser(userId)
                // try to update local cached profile followers_count if present
                val current = _profile.value
                if (current != null) {
                    // no-op: UI will refresh from server on next load
                }
            } catch (_: Exception) {
            }
        }
    }

    fun sendMessage(userId: String, body: String) {
        viewModelScope.launch {
            try {
                val payload = JsonObject(mapOf("to_user_id" to kotlinx.serialization.json.JsonPrimitive(userId.toLong()), "body" to kotlinx.serialization.json.JsonPrimitive(body)))
                api.sendMessage(payload)
            } catch (_: Exception) {
            }
        }
    }
}
