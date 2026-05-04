package com.wallfruits.app

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF275D38),
    onPrimary = Color.White,
    secondary = Color(0xFF8F6B2E),
    onSecondary = Color.White,
    background = Color(0xFFF7F4EE),
    onBackground = Color(0xFF1E1E1E),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1E1E1E),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9DD6A4),
    onPrimary = Color(0xFF11301D),
    secondary = Color(0xFFE7C36A),
    onSecondary = Color(0xFF3A2D09),
    background = Color(0xFF121612),
    onBackground = Color(0xFFF3F3F3),
    surface = Color(0xFF1A201A),
    onSurface = Color(0xFFF3F3F3),
)

@Composable
fun WallFruitsTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = Typography(),
        content = content,
    )
}
