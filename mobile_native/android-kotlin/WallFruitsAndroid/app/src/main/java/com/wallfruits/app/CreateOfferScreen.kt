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
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import javax.inject.Inject

data class CreateOfferFormState(
    val productName: String = "",
    val description: String = "",
    val price: String = "",
    val unit: String = "kg",
    val location: String = "",
    val quantity: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class CreateOfferViewModel @Inject constructor(
    private val api: AuthApi,
) : ViewModel() {
    private val _state = MutableStateFlow(CreateOfferFormState())
    val state = _state.asStateFlow()

    fun updateProductName(value: String) {
        _state.value = _state.value.copy(productName = value)
    }

    fun updateDescription(value: String) {
        _state.value = _state.value.copy(description = value)
    }

    fun updatePrice(value: String) {
        _state.value = _state.value.copy(price = value)
    }

    fun updateUnit(value: String) {
        _state.value = _state.value.copy(unit = value)
    }

    fun updateLocation(value: String) {
        _state.value = _state.value.copy(location = value)
    }

    fun updateQuantity(value: String) {
        _state.value = _state.value.copy(quantity = value)
    }

    fun submitOffer(snackbar: SnackbarViewModel) {
        val current = _state.value
        if (current.productName.trim().isEmpty() || current.price.trim().isEmpty()) {
            snackbar.showMessage("Preencha todos os campos obrigatórios", SnackbarType.WARNING)
            return
        }

        _state.value = current.copy(isLoading = true, error = null)
        viewModelScope.launch {
            try {
                val body = buildJsonObject {
                    put("product_name", current.productName)
                    put("description", current.description)
                    put("price", current.price.toDoubleOrNull() ?: 0.0)
                    put("unit", current.unit)
                    put("location", current.location)
                    put("quantity", current.quantity)
                }
                // TODO: call API endpoint to create offer (e.g., /api/offers/create)
                _state.value = CreateOfferFormState() // reset form
                snackbar.showMessage("Oferta criada com sucesso!", SnackbarType.SUCCESS)
            } catch (e: Exception) {
                _state.value = current.copy(isLoading = false, error = e.message)
                snackbar.showMessage("Erro ao criar oferta", SnackbarType.ERROR)
            }
        }
    }
}

@Composable
fun CreateOfferScreen() {
    val vm: CreateOfferViewModel = hiltViewModel()
    val snackbar = remember { SnackbarViewModel() }
    val state by vm.state.collectAsState()

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxSize()
                .verticalScroll(androidx.compose.foundation.rememberScrollState())
        ) {
            TopAppBar(title = { Text("Criar Oferta") })

            TextField(
                value = state.productName,
                onValueChange = { vm.updateProductName(it) },
                label = { Text("Nome do Produto") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
            )

            TextField(
                value = state.description,
                onValueChange = { vm.updateDescription(it) },
                label = { Text("Descrição") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                maxLines = 3,
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                TextField(
                    value = state.price,
                    onValueChange = { vm.updatePrice(it) },
                    label = { Text("Preço") },
                    modifier = Modifier.weight(1f),
                )
                TextField(
                    value = state.unit,
                    onValueChange = { vm.updateUnit(it) },
                    label = { Text("Unidade") },
                    modifier = Modifier.weight(0.8f),
                )
            }

            TextField(
                value = state.quantity,
                onValueChange = { vm.updateQuantity(it) },
                label = { Text("Quantidade") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 12.dp),
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
                onClick = { vm.submitOffer(snackbar) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 24.dp),
                enabled = !state.isLoading,
            ) {
                Text(if (state.isLoading) "Criando..." else "Criar Oferta")
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
