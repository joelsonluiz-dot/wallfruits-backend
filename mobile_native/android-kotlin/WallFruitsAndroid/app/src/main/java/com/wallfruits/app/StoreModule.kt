package com.wallfruits.app

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun StoreModuleContent(state: AuthUiState, onRefresh: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        RowHeader(title = "Loja", onRefresh = onRefresh)

        if (state.isModuleLoading) {
            Text("Carregando loja...", style = MaterialTheme.typography.bodyMedium)
            return
        }
        state.moduleErrorMessage?.let { message ->
            Text(message, style = MaterialTheme.typography.bodyMedium)
            return
        }

        val items = if (state.serviceItems.isNotEmpty()) {
            state.serviceItems.map { StoreItemPreview(it.id, it.title, "${it.price}") }
        } else {
            // placeholder demo items when backend module not yet implemented
            listOf(
                StoreItemPreview("demo-1", "Fertilizante Orgânico", "R$ 45,00"),
                StoreItemPreview("demo-2", "Semente Milho Premium", "R$ 120,00"),
                StoreItemPreview("demo-3", "Adubo NPK 10-20-10", "R$ 78,00"),
                StoreItemPreview("demo-4", "Inseticida Natural", "R$ 32,50"),
                StoreItemPreview("demo-5", "Ferramenta Manual", "R$ 89,90"),
                StoreItemPreview("demo-6", "Rede de Proteção", "R$ 59,00"),
            )
        }

        LazyVerticalGrid(
            columns = GridCells.Adaptive(minSize = UiDimens.cardMinWidth),
            contentPadding = PaddingValues(8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            items(items, key = { it.id }) { item ->
                StandardCardContainer(modifier = Modifier) {
                    StandardImagePlaceholder()
                    Text(item.title, style = MaterialTheme.typography.titleMedium, maxLines = 2)
                    Text(item.price, style = MaterialTheme.typography.bodyMedium)
                    androidx.compose.foundation.layout.Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        StandardButton(text = "Ver", onClick = { /* abrir detalhe */ })
                    }
                }
            }
        }
    }
}

@Composable
private fun RowHeader(title: String, onRefresh: () -> Unit) {
    androidx.compose.foundation.layout.Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, style = MaterialTheme.typography.headlineSmall)
        TextButton(onClick = onRefresh) { Text("Atualizar módulo") }
    }
}

// StandardCard moved to StandardComponents.kt

data class StoreItemPreview(val id: String, val title: String, val price: String)
