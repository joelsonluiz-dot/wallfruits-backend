package com.wallfruits.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            WallFruitsApp()
        }
    }
}

@Composable
fun WallFruitsApp() {
    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier) {
        val viewModel: HomeViewModel = hiltViewModel()
        HomeScreen(viewModel = viewModel)
    }
}
