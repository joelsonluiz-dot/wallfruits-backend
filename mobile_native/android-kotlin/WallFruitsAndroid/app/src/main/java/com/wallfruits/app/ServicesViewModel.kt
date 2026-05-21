package com.wallfruits.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ServicesViewModel @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {
    private val _services = MutableStateFlow<List<ServiceItem>>(emptyList())
    val services = _services.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            try {
                val resp = api.services(skip = 0, limit = 50)
                _services.value = resp.services.map { ServiceItem(it.id, it.title ?: "Serviço") }
            } catch (e: Exception) {
                // ignore
            }
        }
    }
}

data class ServiceItem(val id: Long, val title: String)
