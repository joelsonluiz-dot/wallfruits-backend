Kotlin Multiplatform scaffold for WallFruits

This folder contains a minimal scaffold for Kotlin Multiplatform (KMM) + Compose Multiplatform.

Modules:
- `shared` - KMM shared code (Ktor client, models, business logic)
- `androidApp` - Android application module (Kotlin + Compose for Android)
- `webApp` - Web target using Kotlin/JS + Compose for Web
- `iosApp` - placeholder for iOS Xcode project (use `shared` artifacts)

Next steps:
1. Install a compatible Gradle (or use Gradle wrapper) and Kotlin plugin (1.9+ recommended).
2. From `kmm/` run `./gradlew assemble` to verify configuration (may require Android SDK / Xcode).
3. Integrate API endpoints and UI components into `shared`.

CI and build hints:
- A GitHub Actions workflow was added at `.github/workflows/kmm-ci.yml` which runs `./kmm/gradlew assemble` on main pushes/PRs.
- To build web app: `cd kmm && ./gradlew :webApp:browserProductionWebpack` (requires Node toolchain installed by Gradle).
- To build android: open `kmm` in Android Studio or run `./gradlew :androidApp:assembleDebug` (requires Android SDK).
- To build iOS: produce an XCFramework from `:shared` and integrate into Xcode (see Kotlin Multiplatform docs).

This scaffold is intentionally minimal—I'll expand targets, add platform-specific engine configs, and CI matrix (macOS build for iOS) if you want me to continue.
