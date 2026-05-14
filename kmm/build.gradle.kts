plugins {
    kotlin("multiplatform") version "1.9.20" apply false
    id("org.jetbrains.compose") version "1.5.0" apply false
}

allprojects {
    repositories {
        mavenCentral()
        google()
        maven("https://maven.pkg.jetbrains.space/public/p/compose/dev")
    }
}
