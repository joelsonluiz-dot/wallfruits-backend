# WallFruits Project Guidelines

## Platform Stack
- Default to native Android in Kotlin.
- Default to native iOS in Swift.
- Default to desktop clients in React/TypeScript.
- Do not introduce Flutter, React Native, or other cross-platform substitutes unless the user explicitly asks for them.
- Treat "Instagram-like" as a UX reference only, not a stack choice.

## Architecture
- Keep the existing stack for each layer unless a task explicitly requests a migration.
- Android work should stay in Kotlin-based native Android code.
- iOS work should stay in Swift-based native iOS code.
- Desktop work should stay in React/TypeScript.
- Backend changes should preserve the current Python service architecture unless the request says otherwise.

## Conventions
- Assume native implementations for mobile features by default.
- When a request is ambiguous about platform, choose the native stack above instead of a cross-platform framework.
- Use the repository's existing codebase and docs as the source of truth for each platform-specific implementation.