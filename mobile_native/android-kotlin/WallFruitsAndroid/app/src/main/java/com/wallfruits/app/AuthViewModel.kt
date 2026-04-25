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
            refreshHomeData()
        }
    }

    fun updateName(value: String) {
        _state.update { it.copy(name = value) }
    }

    fun updateEmail(value: String) {
        _state.update { it.copy(email = value) }
    }

    fun updatePassword(value: String) {
        _state.update { it.copy(password = value) }
    }

    fun setAuthMode(mode: AuthMode) {
        _state.update { it.copy(authMode = mode, errorMessage = null) }
    }

    fun setRole(role: String) {
        _state.update { it.copy(role = role) }
    }

    fun selectModule(module: AppModuleTab) {
        _state.update { it.copy(selectedModule = module) }
    }

    fun submitAuth() {
        if (_state.value.authMode == AuthMode.REGISTER) {
            register()
        } else {
            login()
        }
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
                refreshHomeData()
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

    fun register() {
        val current = _state.value
        _state.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            runCatching {
                repository.register(
                    name = current.name,
                    email = current.email,
                    password = current.password,
                    role = current.role,
                )
                repository.login(current.email, current.password)
            }.onSuccess { user ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        isLoggedIn = true,
                        userName = user.name,
                        authMode = AuthMode.LOGIN,
                        errorMessage = null,
                    )
                }
                refreshHomeData()
            }.onFailure { throwable ->
                _state.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = throwable.message ?: "Falha ao criar conta",
                    )
                }
            }
        }
    }

    fun refreshDashboard() = refreshHomeData()

    fun refreshHomeData() {
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

            runCatching {
                repository.loadNativeModulesSnapshot()
            }.onSuccess { snapshot ->
                _state.update {
                    it.copy(
                        communityTotal = snapshot.communityTotal,
                        servicesTotal = snapshot.servicesTotal,
                        managedServicesTotal = snapshot.managedServicesTotal,
                        clientsTotal = snapshot.clientsTotal,
                        libraryTotal = snapshot.libraryTotal,
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

enum class AuthMode {
    LOGIN,
    REGISTER,
}

enum class AppModuleTab(val title: String) {
    INICIO("Inicio"),
    COMUNIDADE("Comunidade"),
    SERVICOS("Servicos"),
    GERIR_SERVICOS("Gerir servicos"),
    MEUS_CLIENTES("Meus clientes"),
    BIBLIOTECA("Biblioteca"),
    LOJA_AGRICOLA("Loja Agricola"),
    PAINEL_DA_LOJA("Painel da Loja"),
}

data class AuthUiState(
    val authMode: AuthMode = AuthMode.LOGIN,
    val name: String = "",
    val email: String = "",
    val password: String = "",
    val role: String = "buyer",
    val isLoading: Boolean = false,
    val isLoggedIn: Boolean = false,
    val userName: String? = null,
    val errorMessage: String? = null,
    val selectedModule: AppModuleTab = AppModuleTab.INICIO,
    val offersTotal: Int = 0,
    val ordersTotal: Int = 0,
    val aiSignals: Int = 0,
    val communityTotal: Int = 0,
    val servicesTotal: Int = 0,
    val managedServicesTotal: Int = 0,
    val clientsTotal: Int = 0,
    val libraryTotal: Int = 0,
)
