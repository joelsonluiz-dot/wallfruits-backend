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

    fun clearModuleActionMessage() {
        _state.update { it.copy(moduleActionMessage = null) }
    }

    fun selectModule(module: AppModuleTab) {
        _state.update { it.copy(selectedModule = module) }
        loadSelectedModuleData(module = module)
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

    fun createManagedService(
        title: String,
        description: String,
        price: String,
        location: String,
    ) {
        if (title.trim().length < 3 || description.trim().length < 10 || price.trim().length < 2 || location.trim().length < 2) {
            _state.update { it.copy(moduleErrorMessage = "Preencha os campos do servico com dados validos") }
            return
        }

        _state.update { it.copy(isModuleSaving = true, moduleErrorMessage = null, moduleActionMessage = null) }
        viewModelScope.launch {
            runCatching {
                repository.createManagedService(
                    title = title,
                    description = description,
                    price = price,
                    location = location,
                )
            }.onSuccess {
                _state.update {
                    it.copy(
                        isModuleSaving = false,
                        moduleErrorMessage = null,
                        moduleActionMessage = "Servico criado com sucesso",
                    )
                }
                loadSelectedModuleData(module = AppModuleTab.GERIR_SERVICOS, force = true)
                refreshHomeData()
            }.onFailure { throwable ->
                _state.update {
                    it.copy(
                        isModuleSaving = false,
                        moduleErrorMessage = throwable.message ?: "Falha ao criar servico",
                    )
                }
            }
        }
    }

    fun createBuyerClient(
        name: String,
        company: String,
        city: String,
        state: String,
        managementScope: String,
    ) {
        if (name.trim().length < 2) {
            _state.update { it.copy(moduleErrorMessage = "Nome do cliente precisa de pelo menos 2 caracteres") }
            return
        }

        _state.update { it.copy(isModuleSaving = true, moduleErrorMessage = null, moduleActionMessage = null) }
        viewModelScope.launch {
            runCatching {
                repository.createBuyerClient(
                    name = name,
                    company = company,
                    city = city,
                    state = state,
                    managementScope = managementScope,
                )
            }.onSuccess {
                _state.update {
                    it.copy(
                        isModuleSaving = false,
                        moduleErrorMessage = null,
                        moduleActionMessage = "Cliente criado com sucesso",
                    )
                }
                loadSelectedModuleData(module = AppModuleTab.MEUS_CLIENTES, force = true)
                refreshHomeData()
            }.onFailure { throwable ->
                _state.update {
                    it.copy(
                        isModuleSaving = false,
                        moduleErrorMessage = throwable.message ?: "Falha ao criar cliente",
                    )
                }
            }
        }
    }

    fun refreshSelectedModule() {
        loadSelectedModuleData(module = _state.value.selectedModule, force = true)
    }

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

            loadSelectedModuleData(module = _state.value.selectedModule, force = true)
        }
    }

    private fun loadSelectedModuleData(module: AppModuleTab, force: Boolean = false) {
        when (module) {
            AppModuleTab.COMUNIDADE -> {
                if (!force && _state.value.communityItems.isNotEmpty()) {
                    return
                }
                _state.update { it.copy(isModuleLoading = true, moduleErrorMessage = null) }
                viewModelScope.launch {
                    runCatching { repository.loadCommunityPreview() }
                        .onSuccess { items ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = null,
                                    communityItems = items,
                                    communityTotal = if (it.communityTotal == 0) items.size else it.communityTotal,
                                )
                            }
                        }
                        .onFailure { throwable ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = throwable.message ?: "Falha ao carregar comunidade",
                                )
                            }
                        }
                }
            }

            AppModuleTab.SERVICOS -> {
                if (!force && _state.value.serviceItems.isNotEmpty()) {
                    return
                }
                _state.update { it.copy(isModuleLoading = true, moduleErrorMessage = null) }
                viewModelScope.launch {
                    runCatching { repository.loadServicesPreview() }
                        .onSuccess { items ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = null,
                                    serviceItems = items,
                                    servicesTotal = if (it.servicesTotal == 0) items.size else it.servicesTotal,
                                )
                            }
                        }
                        .onFailure { throwable ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = throwable.message ?: "Falha ao carregar servicos",
                                )
                            }
                        }
                }
            }

            AppModuleTab.GERIR_SERVICOS -> {
                if (!force && _state.value.managedServiceItems.isNotEmpty()) {
                    return
                }
                _state.update { it.copy(isModuleLoading = true, moduleErrorMessage = null) }
                viewModelScope.launch {
                    runCatching { repository.loadManagedServicesPreview() }
                        .onSuccess { items ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = null,
                                    managedServiceItems = items,
                                    managedServicesTotal = if (it.managedServicesTotal == 0) items.size else it.managedServicesTotal,
                                )
                            }
                        }
                        .onFailure { throwable ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = throwable.message ?: "Falha ao carregar servicos gerenciados",
                                )
                            }
                        }
                }
            }

            AppModuleTab.MEUS_CLIENTES -> {
                if (!force && _state.value.clientItems.isNotEmpty()) {
                    return
                }
                _state.update { it.copy(isModuleLoading = true, moduleErrorMessage = null) }
                viewModelScope.launch {
                    runCatching { repository.loadBuyerClientsPreview() }
                        .onSuccess { items ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = null,
                                    clientItems = items,
                                    clientsTotal = if (it.clientsTotal == 0) items.size else it.clientsTotal,
                                )
                            }
                        }
                        .onFailure { throwable ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = throwable.message ?: "Falha ao carregar clientes",
                                )
                            }
                        }
                }
            }

            AppModuleTab.BIBLIOTECA -> {
                if (!force && _state.value.libraryItems.isNotEmpty()) {
                    return
                }
                _state.update { it.copy(isModuleLoading = true, moduleErrorMessage = null) }
                viewModelScope.launch {
                    runCatching { repository.loadLibraryPreview() }
                        .onSuccess { items ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = null,
                                    libraryItems = items,
                                    libraryTotal = if (it.libraryTotal == 0) items.size else it.libraryTotal,
                                )
                            }
                        }
                        .onFailure { throwable ->
                            _state.update {
                                it.copy(
                                    isModuleLoading = false,
                                    moduleErrorMessage = throwable.message ?: "Falha ao carregar biblioteca",
                                )
                            }
                        }
                }
            }

            else -> {
                _state.update { it.copy(isModuleLoading = false, moduleErrorMessage = null) }
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
    val isModuleLoading: Boolean = false,
    val isModuleSaving: Boolean = false,
    val moduleErrorMessage: String? = null,
    val moduleActionMessage: String? = null,
    val communityItems: List<CommunityPreview> = emptyList(),
    val serviceItems: List<ServicePreview> = emptyList(),
    val managedServiceItems: List<ServicePreview> = emptyList(),
    val clientItems: List<BuyerClientPreview> = emptyList(),
    val libraryItems: List<LibraryPreview> = emptyList(),
)
