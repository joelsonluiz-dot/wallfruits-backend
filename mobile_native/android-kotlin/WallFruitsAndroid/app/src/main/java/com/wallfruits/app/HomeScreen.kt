package com.wallfruits.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun HomeScreen(viewModel: AuthViewModel) {
    val state = viewModel.state.collectAsState().value

    Scaffold(
        bottomBar = {
            NavigationBar {
                listOf("Feed", "Market", "AI").forEachIndexed { index, label ->
                    NavigationBarItem(
                        selected = index == 0,
                        onClick = { },
                        label = { Text(label) },
                        icon = {},
                    )
                }
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = "WallFruits Android",
                style = MaterialTheme.typography.headlineMedium,
            )
            Text(
                text = "JWT ativo para ${state.userName ?: "usuario"}",
                style = MaterialTheme.typography.bodyMedium,
            )
            Button(onClick = viewModel::logout) {
                Text("Sair")
            }
        }
    }
}
