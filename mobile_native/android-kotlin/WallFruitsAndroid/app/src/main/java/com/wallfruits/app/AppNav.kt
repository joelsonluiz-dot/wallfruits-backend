package com.wallfruits.app

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Text
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

sealed class Screen(val key: String, val label: String) {
    object Home : Screen("home", "Home")
    object Offers : Screen("offers", "Ofertas")
    object Services : Screen("services", "Serviços")
    object Profile : Screen("profile", "Perfil")
    object Community : Screen("community", "Comunidade")
    object Form : Screen("form", "Cadastro")
}

@Composable
fun AppNav() {
    val current = remember { mutableStateOf<Screen>(Screen.Home) }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.padding(bottom = 0.dp)) {
            TopAppBar(title = { Text(current.value.label) })

            when (current.value) {
                is Screen.Home -> HomeScreen()
                is Screen.Offers -> OffersScreen()
                is Screen.Services -> ServicesScreen()
                is Screen.Profile -> ProfileScreen()
                is Screen.Community -> CommunityScreen()
                is Screen.Form -> PremiumFruitFormScreen(onLogout = {}, onRefresh = {})
            }

            NavigationBar {
                NavigationBarItem(selected = current.value is Screen.Home, onClick = { current.value = Screen.Home }, icon = { Text("🏠") }, label = { Text("Home") })
                NavigationBarItem(selected = current.value is Screen.Offers, onClick = { current.value = Screen.Offers }, icon = { Text("🧾") }, label = { Text("Ofertas") })
                NavigationBarItem(selected = current.value is Screen.Services, onClick = { current.value = Screen.Services }, icon = { Text("🔧") }, label = { Text("Serviços") })
                NavigationBarItem(selected = current.value is Screen.Community, onClick = { current.value = Screen.Community }, icon = { Text("💬") }, label = { Text("Comunidade") })
                NavigationBarItem(selected = current.value is Screen.Profile, onClick = { current.value = Screen.Profile }, icon = { Text("👤") }, label = { Text("Perfil") })
            }
        }
    }
}
