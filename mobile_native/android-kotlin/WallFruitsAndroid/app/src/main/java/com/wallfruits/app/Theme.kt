package com.wallfruits.app

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColors = darkColorScheme(
    primary = Color(0xFF6C63FF),
    onPrimary = Color.White,
    secondary = Color(0xFF00D4FF),
    onSecondary = Color(0xFF08111F),
    tertiary = Color(0xFF8B5CF6),
    background = Color(0xFF0B0F1A),
    onBackground = Color(0xFFF8FAFF),
    surface = Color(0xFF121826),
    onSurface = Color(0xFFF8FAFF),
)

@Composable
fun WallFruitsTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography = Typography(),
        content = content,
    )
}
