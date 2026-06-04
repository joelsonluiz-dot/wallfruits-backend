package com.wallfruits.app

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class SnackbarMessage(
    val id: Long = System.currentTimeMillis(),
    val message: String,
    val type: SnackbarType = SnackbarType.INFO,
)

enum class SnackbarType {
    INFO, SUCCESS, ERROR, WARNING
}

class SnackbarViewModel : ViewModel() {
    private val _messages = MutableStateFlow<List<SnackbarMessage>>(emptyList())
    val messages: StateFlow<List<SnackbarMessage>> = _messages.asStateFlow()

    fun showMessage(message: String, type: SnackbarType = SnackbarType.INFO) {
        val snack = SnackbarMessage(message = message, type = type)
        _messages.update { it + snack }
        // auto-remove after 3 seconds
        kotlinx.coroutines.GlobalScope.launch {
            kotlinx.coroutines.delay(3000)
            _messages.update { list -> list.filter { it.id != snack.id } }
        }
    }

    fun removeMessage(id: Long) {
        _messages.update { it.filter { msg -> msg.id != id } }
    }
}
