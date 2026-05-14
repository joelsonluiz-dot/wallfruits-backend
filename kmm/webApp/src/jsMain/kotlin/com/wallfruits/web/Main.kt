package com.wallfruits.web

import androidx.compose.runtime.*
import org.jetbrains.compose.web.css.*
import org.jetbrains.compose.web.dom.*
import org.jetbrains.compose.web.renderComposable

fun main() {
    renderComposable(rootElementId = "root") {
        App()
    }
}

@Composable
fun App() {
    Style(AppStyles)
    Div(attrs = { classes(AppStyles.container) }) {
        H1 { Text("WallFruits - Store (Compose Web sample)") }
        P { Text("This is a lightweight demo UI built with Compose for Web. Connect to shared ApiClient for real data.") }
    }
}

object AppStyles : StyleSheet() {
    val container by style {
        property("max-width", "880px")
        margin(0.px, auto)
        padding(16.px)
        fontFamily("Manrope, Arial, sans-serif")
    }
}
