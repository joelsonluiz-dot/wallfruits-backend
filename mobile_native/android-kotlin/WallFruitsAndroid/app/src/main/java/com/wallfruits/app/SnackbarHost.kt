package com.wallfruits.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically

@Composable
fun SnackbarHost(
    messages: List<SnackbarMessage>,
    modifier: Modifier = Modifier,
    onRemove: (Long) -> Unit = {},
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(16.dp),
        verticalArrangement = Arrangement.Bottom,
    ) {
        messages.forEach { snack ->
            AnimatedVisibility(
                visible = true,
                enter = slideInVertically(initialOffsetY = { it }),
                exit = slideOutVertically(targetOffsetY = { it }),
            ) {
                SnackbarItem(snack, onRemove)
            }
        }
    }
}

@Composable
fun SnackbarItem(message: SnackbarMessage, onRemove: (Long) -> Unit) {
    val bgColor = when (message.type) {
        SnackbarType.SUCCESS -> Color(0xFF4CAF50)
        SnackbarType.ERROR -> Color(0xFFF44336)
        SnackbarType.WARNING -> Color(0xFFFFC107)
        SnackbarType.INFO -> Color(0xFF2196F3)
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(bgColor, shape = androidx.compose.foundation.shape.RoundedCornerShape(8.dp))
            .padding(12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = message.message,
            color = Color.White,
            style = MaterialTheme.typography.bodySmall,
        )
    }
    Spacer(modifier = Modifier.height(8.dp))
}
