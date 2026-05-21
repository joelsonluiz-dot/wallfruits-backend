package com.wallfruits.app

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState

@Composable
fun AuthGate(viewModel: AuthViewModel) {
    val state = viewModel.state.collectAsState().value
    if (state.isLoggedIn) {
        PremiumFruitFormScreen(
            onLogout = viewModel::logout,
            onRefresh = viewModel::refreshDashboard,
        )
    } else {
        LoginScreen(viewModel = viewModel)
    }
}
