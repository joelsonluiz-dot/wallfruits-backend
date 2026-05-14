plugins {
    id("com.android.application") version "8.1.0" apply false
    kotlin("android") version "1.9.20" apply false
}

android {
    namespace = "com.wallfruits.android"
    compileSdk = 34
}

dependencies {
    implementation(project(":shared"))
}
