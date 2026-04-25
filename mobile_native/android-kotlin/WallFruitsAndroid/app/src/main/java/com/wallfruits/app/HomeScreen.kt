package com.wallfruits.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.material3.rememberDrawerState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(viewModel: AuthViewModel) {
    val state = viewModel.state.collectAsState().value
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val coroutineScope = rememberCoroutineScope()

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet {
                Text(
                    text = "WallFruits - Modulos",
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 20.dp),
                    style = MaterialTheme.typography.titleMedium,
                )
                AppModuleTab.entries.forEach { module ->
                    NavigationDrawerItem(
                        label = { Text(module.title) },
                        selected = state.selectedModule == module,
                        onClick = {
                            viewModel.selectModule(module)
                            coroutineScope.launch { drawerState.close() }
                        },
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 2.dp),
                    )
                }
            }
        },
    ) { padding ->
        Scaffold(
            modifier = Modifier.padding(padding),
            topBar = {
                TopAppBar(
                    title = { Text("WallFruits Android") },
                    navigationIcon = {
                        TextButton(onClick = { coroutineScope.launch { drawerState.open() } }) {
                            Text("Menu")
                        }
                    },
                    actions = {
                        TextButton(onClick = viewModel::refreshHomeData) {
                            Text("Atualizar")
                        }
                    },
                )
            },
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(it)
                    .padding(20.dp),
                verticalArrangement = Arrangement.Top,
                horizontalAlignment = Alignment.Start,
            ) {
                Text(
                    text = "Sessao ativa: ${state.userName ?: "usuario"}",
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Feed ${state.offersTotal} | Marketplace ${state.ordersTotal} | IA ${state.aiSignals}",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Comunidade ${state.communityTotal} | Servicos ${state.servicesTotal} | Biblioteca ${state.libraryTotal}",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(modifier = Modifier.height(16.dp))

                ModulePanel(
                    state = state,
                    onRefreshSelectedModule = viewModel::refreshSelectedModule,
                    onCreateManagedService = viewModel::createManagedService,
                    onUpdateManagedService = viewModel::updateManagedService,
                    onDeleteManagedService = viewModel::deleteManagedService,
                    onCreateBuyerClient = viewModel::createBuyerClient,
                    onUpdateBuyerClient = viewModel::updateBuyerClient,
                    onDeleteBuyerClient = viewModel::deleteBuyerClient,
                    onClearModuleActionMessage = viewModel::clearModuleActionMessage,
                )

                Spacer(modifier = Modifier.height(20.dp))
                Row(modifier = Modifier.fillMaxWidth()) {
                    Button(onClick = viewModel::refreshHomeData) {
                        Text("Atualizar dados")
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Button(onClick = viewModel::logout) {
                        Text("Sair")
                    }
                }
            }
        }
    }
}

@Composable
private fun ModulePanel(
    state: AuthUiState,
    onRefreshSelectedModule: () -> Unit,
    onCreateManagedService: (String, String, String, String) -> Unit,
    onUpdateManagedService: (String, String, String, String, String) -> Unit,
    onDeleteManagedService: (String) -> Unit,
    onCreateBuyerClient: (String, String, String, String, String) -> Unit,
    onUpdateBuyerClient: (String, String, String, String, String, String) -> Unit,
    onDeleteBuyerClient: (String) -> Unit,
    onClearModuleActionMessage: () -> Unit,
) {
    when (state.selectedModule) {
        AppModuleTab.COMUNIDADE -> CommunityModuleContent(state = state, onRefresh = onRefreshSelectedModule)
        AppModuleTab.SERVICOS -> ServicesModuleContent(state = state, onRefresh = onRefreshSelectedModule)
        AppModuleTab.GERIR_SERVICOS -> ManagedServicesModuleContent(
            state = state,
            onRefresh = onRefreshSelectedModule,
            onCreate = onCreateManagedService,
            onUpdate = onUpdateManagedService,
            onDelete = onDeleteManagedService,
            onClearMessage = onClearModuleActionMessage,
        )
        AppModuleTab.MEUS_CLIENTES -> ClientsModuleContent(
            state = state,
            onRefresh = onRefreshSelectedModule,
            onCreate = onCreateBuyerClient,
            onUpdate = onUpdateBuyerClient,
            onDelete = onDeleteBuyerClient,
            onClearMessage = onClearModuleActionMessage,
        )
        AppModuleTab.BIBLIOTECA -> LibraryModuleContent(state = state, onRefresh = onRefreshSelectedModule)
        else -> GenericModuleContent(state = state)
    }
}

@Composable
private fun GenericModuleContent(state: AuthUiState) {
    val (title, subtitle) = when (state.selectedModule) {
        AppModuleTab.INICIO -> "Inicio" to "Resumo geral da plataforma com Feed, Marketplace e IA."
        AppModuleTab.LOJA_AGRICOLA -> "Loja Agricola" to "Fluxo da loja preservado junto ao Marketplace (pedidos ${state.ordersTotal})."
        AppModuleTab.PAINEL_DA_LOJA -> "Painel da Loja" to "Modulo do painel da loja pronto para evolucao nativa por sprint."
        AppModuleTab.GERIR_SERVICOS -> "Gerir servicos" to "Servicos sob gestao: ${state.managedServicesTotal}."
        AppModuleTab.MEUS_CLIENTES -> "Meus clientes" to "Clientes cadastrados no modulo: ${state.clientsTotal}."
        AppModuleTab.BIBLIOTECA -> "Biblioteca" to "Itens publicados na biblioteca: ${state.libraryTotal}."
        AppModuleTab.COMUNIDADE -> "Comunidade" to "Posts da comunidade disponiveis: ${state.communityTotal}."
        AppModuleTab.SERVICOS -> "Servicos" to "Servicos publicos cadastrados: ${state.servicesTotal}."
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(text = title, style = MaterialTheme.typography.headlineSmall)
        Text(text = subtitle, style = MaterialTheme.typography.bodyLarge)
        Text(
            text = "Migracao nativa ativa: modulo funcional com dados reais e sem quebra de sessao.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun CommunityModuleContent(state: AuthUiState, onRefresh: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Comunidade", style = MaterialTheme.typography.headlineSmall)
            TextButton(onClick = onRefresh) { Text("Atualizar modulo") }
        }
        Text("Posts encontrados: ${state.communityTotal}", style = MaterialTheme.typography.bodyMedium)
        if (state.isModuleLoading) {
            Text("Carregando posts...", style = MaterialTheme.typography.bodyMedium)
            return
        }
        state.moduleErrorMessage?.let { message ->
            Text(message, style = MaterialTheme.typography.bodyMedium)
            return
        }
        if (state.communityItems.isEmpty()) {
            Text("Nenhum post disponivel no momento.", style = MaterialTheme.typography.bodyMedium)
            return
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .height(280.dp),
            contentPadding = PaddingValues(vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.communityItems, key = { it.id }) { item ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(item.author, style = MaterialTheme.typography.titleMedium)
                        Text(item.text, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "Curtidas ${item.likes} | Comentarios ${item.comments}",
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ServicesModuleContent(state: AuthUiState, onRefresh: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Servicos", style = MaterialTheme.typography.headlineSmall)
            TextButton(onClick = onRefresh) { Text("Atualizar modulo") }
        }
        Text("Servicos encontrados: ${state.servicesTotal}", style = MaterialTheme.typography.bodyMedium)
        if (state.isModuleLoading) {
            Text("Carregando servicos...", style = MaterialTheme.typography.bodyMedium)
            return
        }
        state.moduleErrorMessage?.let { message ->
            Text(message, style = MaterialTheme.typography.bodyMedium)
            return
        }
        if (state.serviceItems.isEmpty()) {
            Text("Nenhum servico disponivel no momento.", style = MaterialTheme.typography.bodyMedium)
            return
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .height(280.dp),
            contentPadding = PaddingValues(vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.serviceItems, key = { it.id }) { item ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(item.title, style = MaterialTheme.typography.titleMedium)
                        Text(item.description, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "Preco ${item.price} | Local ${item.location}",
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ManagedServicesModuleContent(
    state: AuthUiState,
    onRefresh: () -> Unit,
    onCreate: (String, String, String, String) -> Unit,
    onUpdate: (String, String, String, String, String) -> Unit,
    onDelete: (String) -> Unit,
    onClearMessage: () -> Unit,
) {
    var showCreateDialog by remember { mutableStateOf(false) }
    var editingItem by remember { mutableStateOf<ServicePreview?>(null) }
    var deletingItemId by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Gerir servicos", style = MaterialTheme.typography.headlineSmall)
            Row {
                TextButton(onClick = { showCreateDialog = true }) { Text("Novo") }
                TextButton(onClick = onRefresh) { Text("Atualizar") }
            }
        }
        Text("Servicos sob gestao: ${state.managedServicesTotal}", style = MaterialTheme.typography.bodyMedium)
        state.moduleActionMessage?.let { message ->
            TextButton(onClick = onClearMessage, modifier = Modifier.padding(0.dp)) {
                Text(message)
            }
        }
        if (state.isModuleLoading) {
            Text("Carregando servicos gerenciados...", style = MaterialTheme.typography.bodyMedium)
            return
        }
        state.moduleErrorMessage?.let { message ->
            Text(message, style = MaterialTheme.typography.bodyMedium)
            return
        }
        if (state.managedServiceItems.isEmpty()) {
            Text("Nenhum servico em gestao no momento.", style = MaterialTheme.typography.bodyMedium)
            return
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .height(280.dp),
            contentPadding = PaddingValues(vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.managedServiceItems, key = { it.id }) { item ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(item.title, style = MaterialTheme.typography.titleMedium)
                        Text(item.description, style = MaterialTheme.typography.bodyMedium)
                        Text("Preco ${item.price} | Local ${item.location}", style = MaterialTheme.typography.labelMedium)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            TextButton(onClick = { editingItem = item }) { Text("Editar") }
                            TextButton(onClick = { deletingItemId = item.id }) { Text("Excluir") }
                        }
                    }
                }
            }
        }

        if (showCreateDialog) {
            CreateManagedServiceDialog(
                isSaving = state.isModuleSaving,
                onDismiss = { showCreateDialog = false },
                onCreate = { title, description, price, location ->
                    onCreate(title, description, price, location)
                    showCreateDialog = false
                },
            )
        }

        editingItem?.let { item ->
            EditManagedServiceDialog(
                item = item,
                isSaving = state.isModuleSaving,
                onDismiss = { editingItem = null },
                onSave = { title, description, price, location ->
                    onUpdate(item.id, title, description, price, location)
                    editingItem = null
                },
            )
        }

        deletingItemId?.let { serviceId ->
            ConfirmDeleteDialog(
                title = "Excluir servico",
                message = "Tem certeza que deseja excluir este servico?",
                isSaving = state.isModuleSaving,
                onDismiss = { deletingItemId = null },
                onConfirm = {
                    onDelete(serviceId)
                    deletingItemId = null
                },
            )
        }
    }
}

@Composable
private fun ClientsModuleContent(
    state: AuthUiState,
    onRefresh: () -> Unit,
    onCreate: (String, String, String, String, String) -> Unit,
    onUpdate: (String, String, String, String, String, String) -> Unit,
    onDelete: (String) -> Unit,
    onClearMessage: () -> Unit,
) {
    var showCreateDialog by remember { mutableStateOf(false) }
    var editingItem by remember { mutableStateOf<BuyerClientPreview?>(null) }
    var deletingItemId by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Meus clientes", style = MaterialTheme.typography.headlineSmall)
            Row {
                TextButton(onClick = { showCreateDialog = true }) { Text("Novo") }
                TextButton(onClick = onRefresh) { Text("Atualizar") }
            }
        }
        Text("Clientes cadastrados: ${state.clientsTotal}", style = MaterialTheme.typography.bodyMedium)
        state.moduleActionMessage?.let { message ->
            TextButton(onClick = onClearMessage, modifier = Modifier.padding(0.dp)) {
                Text(message)
            }
        }
        if (state.isModuleLoading) {
            Text("Carregando clientes...", style = MaterialTheme.typography.bodyMedium)
            return
        }
        state.moduleErrorMessage?.let { message ->
            Text(message, style = MaterialTheme.typography.bodyMedium)
            return
        }
        if (state.clientItems.isEmpty()) {
            Text("Nenhum cliente encontrado no momento.", style = MaterialTheme.typography.bodyMedium)
            return
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .height(280.dp),
            contentPadding = PaddingValues(vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.clientItems, key = { it.id }) { item ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(item.name, style = MaterialTheme.typography.titleMedium)
                        Text(item.company, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "Cidade/UF ${item.cityState} | Gestao ${item.managementScope}",
                            style = MaterialTheme.typography.labelMedium,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            TextButton(onClick = { editingItem = item }) { Text("Editar") }
                            TextButton(onClick = { deletingItemId = item.id }) { Text("Excluir") }
                        }
                    }
                }
            }
        }

        if (showCreateDialog) {
            CreateBuyerClientDialog(
                isSaving = state.isModuleSaving,
                onDismiss = { showCreateDialog = false },
                onCreate = { name, company, city, uf, scope ->
                    onCreate(name, company, city, uf, scope)
                    showCreateDialog = false
                },
            )
        }

        editingItem?.let { item ->
            EditBuyerClientDialog(
                item = item,
                isSaving = state.isModuleSaving,
                onDismiss = { editingItem = null },
                onSave = { name, company, city, uf, scope ->
                    onUpdate(item.id, name, company, city, uf, scope)
                    editingItem = null
                },
            )
        }

        deletingItemId?.let { clientId ->
            ConfirmDeleteDialog(
                title = "Excluir cliente",
                message = "Tem certeza que deseja excluir este cliente?",
                isSaving = state.isModuleSaving,
                onDismiss = { deletingItemId = null },
                onConfirm = {
                    onDelete(clientId)
                    deletingItemId = null
                },
            )
        }
    }
}

@Composable
private fun LibraryModuleContent(state: AuthUiState, onRefresh: () -> Unit) {
    var selectedItem by remember { mutableStateOf<LibraryPreview?>(null) }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Biblioteca", style = MaterialTheme.typography.headlineSmall)
            TextButton(onClick = onRefresh) { Text("Atualizar modulo") }
        }
        Text("Itens publicados: ${state.libraryTotal}", style = MaterialTheme.typography.bodyMedium)
        if (state.isModuleLoading) {
            Text("Carregando biblioteca...", style = MaterialTheme.typography.bodyMedium)
            return
        }
        state.moduleErrorMessage?.let { message ->
            Text(message, style = MaterialTheme.typography.bodyMedium)
            return
        }
        if (state.libraryItems.isEmpty()) {
            Text("Nenhum item na biblioteca no momento.", style = MaterialTheme.typography.bodyMedium)
            return
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .height(280.dp),
            contentPadding = PaddingValues(vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(state.libraryItems, key = { it.id }) { item ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(item.title, style = MaterialTheme.typography.titleMedium)
                        Text(item.author, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "Categoria ${item.category} | Leitura ${item.readTime}",
                            style = MaterialTheme.typography.labelMedium,
                        )
                        TextButton(onClick = { selectedItem = item }) {
                            Text("Ver detalhe")
                        }
                    }
                }
            }
        }

        selectedItem?.let { item ->
            AlertDialog(
                onDismissRequest = { selectedItem = null },
                title = { Text(item.title) },
                text = {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Autor: ${item.author}")
                        Text("Categoria: ${item.category}")
                        Text("Tempo de leitura: ${item.readTime}")
                        Text("ID: ${item.id}")
                    }
                },
                confirmButton = {
                    TextButton(onClick = { selectedItem = null }) {
                        Text("Fechar")
                    }
                },
            )
        }
    }
}

@Composable
private fun CreateManagedServiceDialog(
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onCreate: (String, String, String, String) -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    var location by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Novo servico") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("Titulo") })
                OutlinedTextField(value = description, onValueChange = { description = it }, label = { Text("Descricao") })
                OutlinedTextField(value = price, onValueChange = { price = it }, label = { Text("Preco") })
                OutlinedTextField(value = location, onValueChange = { location = it }, label = { Text("Local") })
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isSaving) { Text("Cancelar") }
        },
        confirmButton = {
            TextButton(
                enabled = !isSaving,
                onClick = { onCreate(title, description, price, location) },
            ) {
                Text(if (isSaving) "Salvando..." else "Criar")
            }
        },
    )
}

@Composable
private fun CreateBuyerClientDialog(
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onCreate: (String, String, String, String, String) -> Unit,
) {
    var name by remember { mutableStateOf("") }
    var company by remember { mutableStateOf("") }
    var city by remember { mutableStateOf("") }
    var uf by remember { mutableStateOf("") }
    var scope by remember { mutableStateOf("joint") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Novo cliente") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Nome") })
                OutlinedTextField(value = company, onValueChange = { company = it }, label = { Text("Empresa") })
                OutlinedTextField(value = city, onValueChange = { city = it }, label = { Text("Cidade") })
                OutlinedTextField(value = uf, onValueChange = { uf = it }, label = { Text("UF") })
                OutlinedTextField(value = scope, onValueChange = { scope = it }, label = { Text("Gestao (buyer|wallfruits|joint)") })
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isSaving) { Text("Cancelar") }
        },
        confirmButton = {
            TextButton(
                enabled = !isSaving,
                onClick = { onCreate(name, company, city, uf, scope) },
            ) {
                Text(if (isSaving) "Salvando..." else "Criar")
            }
        },
    )
}

@Composable
private fun EditManagedServiceDialog(
    item: ServicePreview,
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onSave: (String, String, String, String) -> Unit,
) {
    var title by remember(item.id) { mutableStateOf(item.title) }
    var description by remember(item.id) { mutableStateOf(item.description) }
    var price by remember(item.id) { mutableStateOf(item.price) }
    var location by remember(item.id) { mutableStateOf(item.location) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Editar servico") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("Titulo") })
                OutlinedTextField(value = description, onValueChange = { description = it }, label = { Text("Descricao") })
                OutlinedTextField(value = price, onValueChange = { price = it }, label = { Text("Preco") })
                OutlinedTextField(value = location, onValueChange = { location = it }, label = { Text("Local") })
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isSaving) { Text("Cancelar") }
        },
        confirmButton = {
            TextButton(enabled = !isSaving, onClick = { onSave(title, description, price, location) }) {
                Text(if (isSaving) "Salvando..." else "Salvar")
            }
        },
    )
}

@Composable
private fun EditBuyerClientDialog(
    item: BuyerClientPreview,
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onSave: (String, String, String, String, String) -> Unit,
) {
    val cityAndUf = item.cityState.split("/")
    var name by remember(item.id) { mutableStateOf(item.name) }
    var company by remember(item.id) { mutableStateOf(item.company) }
    var city by remember(item.id) { mutableStateOf(cityAndUf.getOrNull(0) ?: "") }
    var uf by remember(item.id) { mutableStateOf(cityAndUf.getOrNull(1) ?: "") }
    var scope by remember(item.id) { mutableStateOf(item.managementScope) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Editar cliente") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Nome") })
                OutlinedTextField(value = company, onValueChange = { company = it }, label = { Text("Empresa") })
                OutlinedTextField(value = city, onValueChange = { city = it }, label = { Text("Cidade") })
                OutlinedTextField(value = uf, onValueChange = { uf = it }, label = { Text("UF") })
                OutlinedTextField(value = scope, onValueChange = { scope = it }, label = { Text("Gestao (buyer|wallfruits|joint)") })
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isSaving) { Text("Cancelar") }
        },
        confirmButton = {
            TextButton(enabled = !isSaving, onClick = { onSave(name, company, city, uf, scope) }) {
                Text(if (isSaving) "Salvando..." else "Salvar")
            }
        },
    )
}

@Composable
private fun ConfirmDeleteDialog(
    title: String,
    message: String,
    isSaving: Boolean,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(message) },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !isSaving) { Text("Cancelar") }
        },
        confirmButton = {
            TextButton(onClick = onConfirm, enabled = !isSaving) {
                Text(if (isSaving) "Excluindo..." else "Excluir")
            }
        },
    )
}
