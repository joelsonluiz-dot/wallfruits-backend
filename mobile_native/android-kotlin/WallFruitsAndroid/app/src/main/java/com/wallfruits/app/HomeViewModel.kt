package com.wallfruits.app

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class HomeViewModel : ViewModel() {
    private val _status = MutableStateFlow("ready")
    val status: StateFlow<String> = _status.asStateFlow()

    fun refresh() {
        _status.value = "refreshing"
    }
}
