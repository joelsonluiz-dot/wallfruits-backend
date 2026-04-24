package com.wallfruits.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val repository: AuthRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

    init {
        repository.currentUserName()?.let { userName ->
            _state.update { it.copy(isLoggedIn = true, userName = userName) }
            refreshDashboard()
        }
    }

    fun updateEmail(value: String) {
        _state.update { it.copy(email = value) }
    }

    fun updatePassword(value: String) {
        _state.update { it.copy(password = value) }
    }

    fun login() {
        val current = _state.value
        _state.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            runCatching {
                repository.login(current.email, current.password)
            }.onSuccess { user ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        isLoggedIn = true,
                        userName = user.name,
                        errorMessage = null,
                    )
                }
                refreshDashboard()
            }.onFailure { throwable ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = throwable.message ?: "Falha ao autenticar",
                    )
                }
            }
        }
    }

    fun refreshDashboard() {
        viewModelScope.launch {
            runCatching {
                repository.loadDashboardSnapshot()
            }.onSuccess { snapshot ->
                _state.update {
                    it.copy(
                        offersTotal = snapshot.offersTotal,
                        ordersTotal = snapshot.ordersTotal,
                        aiSignals = snapshot.aiSignals,
                    )
                }
            }
        }
    }

    fun logout() {
        repository.logout()
        _state.value = AuthUiState()
    }
}

data class AuthUiState(
    val email: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val isLoggedIn: Boolean = false,
    val userName: String? = null,
    val errorMessage: String? = null,
    val offersTotal: Int = 0,
    val ordersTotal: Int = 0,
    val aiSignals: Int = 0,
)
