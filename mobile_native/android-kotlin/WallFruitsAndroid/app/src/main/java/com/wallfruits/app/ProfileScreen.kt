package com.wallfruits.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import kotlinx.serialization.json.JsonObject


@Composable
fun ProfileScreen(userId: Long? = null) {
    val vm: ProfileViewModel = hiltViewModel()
    val profile = vm.profile.collectAsState()
    val uid = (userId ?: 0L).toString()

    // trigger load once
    if (profile.value == null && userId != null) {
        vm.load(uid)
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.padding(16.dp)) {
            TopAppBar(title = { Text("Perfil") })

            when (val p = profile.value) {
                null -> Text("Carregando perfil...")
                else -> renderProfileJson(p)
            }
        }
    }
}

@Composable
private fun renderProfileJson(obj: JsonObject) {
    val name = obj["display_name"]?.toString() ?: obj["name"]?.toString() ?: "Perfil"
    val bio = obj["bio"]?.toString() ?: ""
    Text(name.replace('"', ' ').trim(), style = MaterialTheme.typography.titleLarge)
    Text(bio.replace('"', ' ').trim(), style = MaterialTheme.typography.bodyMedium)
}
