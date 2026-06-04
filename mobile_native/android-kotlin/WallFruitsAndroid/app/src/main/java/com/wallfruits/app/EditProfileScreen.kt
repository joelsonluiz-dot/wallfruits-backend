package com.wallfruits.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import javax.inject.Inject

data class EditProfileFormState(
    val name: String = "",
    val bio: String = "",
    val location: String = "",
    val profileImage: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class EditProfileViewModel @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {
    private val _state = MutableStateFlow(EditProfileFormState())
    val state = _state.asStateFlow()

    fun updateName(value: String) {
        _state.value = _state.value.copy(name = value)
    }

    fun updateBio(value: String) {
        _state.value = _state.value.copy(bio = value)
    }

    fun updateLocation(value: String) {
        _state.value = _state.value.copy(location = value)
    }

    fun submitProfile(snackbar: SnackbarViewModel) {
        val current = _state.value
        if (current.name.trim().isEmpty()) {
            snackbar.showMessage("Nome é obrigatório", SnackbarType.WARNING)
            return
        }

        _state.value = current.copy(isLoading = true, error = null)
        viewModelScope.launch {
            try {
                val body = buildJsonObject {
                    put("name", current.name)
                    put("bio", current.bio)
                    put("location", current.location)
                }
                // TODO: call API endpoint to update profile (e.g., /api/profile/update)
                _state.value = current.copy(isLoading = false)
                snackbar.showMessage("Perfil atualizado com sucesso!", SnackbarType.SUCCESS)
            } catch (e: Exception) {
                _state.value = current.copy(isLoading = false, error = e.message)
                snackbar.showMessage("Erro ao atualizar perfil", SnackbarType.ERROR)
            }
        }
    }
}

@Composable
fun EditProfileScreen() {
    val vm: EditProfileViewModel = hiltViewModel()
    val snackbar = remember { SnackbarViewModel() }
    val state by vm.state.collectAsState()

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier
            .padding(16.dp)
            .fillMaxSize()) {
            TopAppBar(title = { Text("Editar Perfil") })

            TextField(
                value = state.name,
                onValueChange = { vm.updateName(it) },
                label = { Text("Nome") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
            )

            TextField(
                value = state.bio,
                onValueChange = { vm.updateBio(it) },
                label = { Text("Bio") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                maxLines = 3,
            )

            TextField(
                value = state.location,
                onValueChange = { vm.updateLocation(it) },
                label = { Text("Localização") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
            )

            Button(
                onClick = { vm.submitProfile(snackbar) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 24.dp),
                enabled = !state.isLoading,
            ) {
                Text(if (state.isLoading) "Salvando..." else "Salvar Perfil")
            }

            if (state.error != null) {
                Text(
                    text = "Erro: ${state.error}",
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }
    }
}
