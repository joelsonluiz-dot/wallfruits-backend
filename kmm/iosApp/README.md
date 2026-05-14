iOS App placeholder

Create an Xcode iOS app target and link the `shared` KMM framework as described in Kotlin Multiplatform docs.

Typical steps:
1. Build `shared` for iOS targets and export XCFramework.
2. Open Xcode, create an iOS app project and add the produced XCFramework.
3. Call shared APIs from Swift/SwiftUI and use Compose Multiplatform for shared UI if desired.
