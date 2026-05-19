package com.wallfruits.app

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF0066FF),
    onPrimary = Color.White,
    secondary = Color(0xFFFF6B00),
    onSecondary = Color.White,
    background = Color(0xFFFFFFFF),
    onBackground = Color(0xFF111827),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF111827),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF66A3FF),
    onPrimary = Color(0xFF0B1F3D),
    secondary = Color(0xFFFFA766),
    onSecondary = Color(0xFF3D1D00),
    background = Color(0xFF0B1020),
    onBackground = Color(0xFFF3F4F6),
    surface = Color(0xFF121A2A),
    onSurface = Color(0xFFF3F4F6),
)

@Composable
fun WallFruitsTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = Typography(),
        content = content,
    )
}
