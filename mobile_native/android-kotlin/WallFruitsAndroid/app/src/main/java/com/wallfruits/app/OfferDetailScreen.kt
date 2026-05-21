package com.wallfruits.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.compose.material3.IconButton
import androidx.compose.material3.Icon
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.ShoppingCart

@Composable
fun OfferDetailScreen(offerId: Long) {
    val actionsVm: OfferActionsViewModel = hiltViewModel()

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.padding(16.dp)) {
            TopAppBar(title = { Text("Detalhe da Oferta") })
            Text("Detalhes da oferta #${offerId} (skeleton)", modifier = Modifier.padding(top = 16.dp))

            // action row
            Column(modifier = Modifier.padding(top = 12.dp)) {
                IconButton(onClick = { actionsVm.toggleFavorite(offerId) }) {
                    Icon(Icons.Filled.Favorite, contentDescription = "Curtir")
                }
                IconButton(onClick = { actionsVm.toggleBookmark(offerId) }) {
                    Icon(Icons.Filled.Bookmark, contentDescription = "Salvar")
                }
                IconButton(onClick = { actionsVm.reserve(offerId, 1, 0.0) }) {
                    Icon(Icons.Filled.ShoppingCart, contentDescription = "Reservar")
                }
            }
        }
    }
}
