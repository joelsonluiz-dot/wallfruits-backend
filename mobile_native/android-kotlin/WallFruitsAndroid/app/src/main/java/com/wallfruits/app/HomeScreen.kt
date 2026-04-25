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
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.rememberCoroutineScope
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
) {
    when (state.selectedModule) {
        AppModuleTab.COMUNIDADE -> CommunityModuleContent(state = state, onRefresh = onRefreshSelectedModule)
        AppModuleTab.SERVICOS -> ServicesModuleContent(state = state, onRefresh = onRefreshSelectedModule)
        AppModuleTab.GERIR_SERVICOS -> ManagedServicesModuleContent(state = state, onRefresh = onRefreshSelectedModule)
        AppModuleTab.MEUS_CLIENTES -> ClientsModuleContent(state = state, onRefresh = onRefreshSelectedModule)
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
private fun ManagedServicesModuleContent(state: AuthUiState, onRefresh: () -> Unit) {
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
            TextButton(onClick = onRefresh) { Text("Atualizar modulo") }
        }
        Text("Servicos sob gestao: ${state.managedServicesTotal}", style = MaterialTheme.typography.bodyMedium)
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
                    }
                }
            }
        }
    }
}

@Composable
private fun ClientsModuleContent(state: AuthUiState, onRefresh: () -> Unit) {
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
            TextButton(onClick = onRefresh) { Text("Atualizar modulo") }
        }
        Text("Clientes cadastrados: ${state.clientsTotal}", style = MaterialTheme.typography.bodyMedium)
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
                    }
                }
            }
        }
    }
}

@Composable
private fun LibraryModuleContent(state: AuthUiState, onRefresh: () -> Unit) {
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
                    }
                }
            }
        }
    }
}
