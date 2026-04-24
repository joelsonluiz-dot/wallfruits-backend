package com.wallfruits.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
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
    WallFruitsTheme {
        Surface {
            val viewModel = androidx.hilt.navigation.compose.hiltViewModel<AuthViewModel>()
            AuthGate(viewModel = viewModel)
        }
    }
}
