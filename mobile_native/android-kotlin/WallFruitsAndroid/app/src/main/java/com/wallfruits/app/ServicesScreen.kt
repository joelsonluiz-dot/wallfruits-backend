package com.wallfruits.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun ServicesScreen() {
    val vm: ServicesViewModel = hiltViewModel()
    val services = vm.services.collectAsState()

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(modifier = Modifier.padding(12.dp)) {
            TopAppBar(title = { Text("Serviços") })

            LazyColumn(modifier = Modifier.padding(top = 12.dp)) {
                items(services.value) { svc ->
                    Card(modifier = Modifier.padding(vertical = 8.dp)) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(svc.title, style = MaterialTheme.typography.titleMedium)
                        }
                    }
                }
            }
        }
    }
}
