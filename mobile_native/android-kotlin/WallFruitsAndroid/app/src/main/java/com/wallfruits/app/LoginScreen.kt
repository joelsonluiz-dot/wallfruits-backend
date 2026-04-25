package com.wallfruits.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

@Composable
fun LoginScreen(viewModel: AuthViewModel) {
    val state = viewModel.state.collectAsState().value
    val isRegister = state.authMode == AuthMode.REGISTER

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = if (isRegister) "Criar conta WallFruits" else "WallFruits Login",
            style = MaterialTheme.typography.headlineMedium,
        )
        Spacer(modifier = Modifier.height(12.dp))
        Row {
            Button(
                onClick = { viewModel.setAuthMode(AuthMode.LOGIN) },
                colors = if (!isRegister) ButtonDefaults.buttonColors() else ButtonDefaults.outlinedButtonColors(),
            ) {
                Text("Login")
            }
            Spacer(modifier = Modifier.width(8.dp))
            Button(
                onClick = { viewModel.setAuthMode(AuthMode.REGISTER) },
                colors = if (isRegister) ButtonDefaults.buttonColors() else ButtonDefaults.outlinedButtonColors(),
            ) {
                Text("Criar conta")
            }
        }
        Spacer(modifier = Modifier.height(16.dp))
        if (isRegister) {
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = state.name,
                onValueChange = viewModel::updateName,
                label = { Text("Nome") },
                singleLine = true,
            )
            Spacer(modifier = Modifier.height(8.dp))
        }
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = state.email,
            onValueChange = viewModel::updateEmail,
            label = { Text("Email") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            singleLine = true,
        )
        Spacer(modifier = Modifier.height(8.dp))
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = state.password,
            onValueChange = viewModel::updatePassword,
            label = { Text("Senha") },
            singleLine = true,
        )
        if (isRegister) {
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                modifier = Modifier.fillMaxWidth(),
                value = state.role,
                onValueChange = viewModel::setRole,
                label = { Text("Perfil (buyer|producer|supplier)") },
                singleLine = true,
            )
        }
        Spacer(modifier = Modifier.height(16.dp))
        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = viewModel::submitAuth,
            enabled = !state.isLoading,
        ) {
            Text(
                if (state.isLoading) {
                    if (isRegister) "Criando conta..." else "Entrando..."
                } else {
                    if (isRegister) "Criar conta" else "Entrar"
                }
            )
        }
        state.errorMessage?.let { message ->
            Spacer(modifier = Modifier.height(12.dp))
            Text(message, color = MaterialTheme.colorScheme.error)
        }
    }
}
