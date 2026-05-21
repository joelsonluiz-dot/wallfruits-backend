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
}
