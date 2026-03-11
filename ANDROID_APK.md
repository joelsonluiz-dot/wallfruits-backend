# APK Android (WallFruits)

Este repositório inclui um app Android WebView em `android/` apontando para:

- https://wallfruits-backend.onrender.com/

## Como baixar APK

1. Abra a aba **Actions** no GitHub.
2. Execute o workflow **Build Android APK**.
3. Ao finalizar, baixe o artefato `wallfruits-android-apk`.
4. Instale o arquivo `app-debug.apk` no Android.

## Observações

- O APK gerado é de debug (ideal para distribuição inicial interna).
- Para loja (Play Store), o próximo passo é gerar build de release com assinatura.

## Experiência de app web (PWA)

Além do APK, o projeto também foi preparado como PWA:

- Manifest: `/static/manifest.webmanifest`
- Service Worker: `/static/sw.js`

No Android (Chrome), também é possível instalar via "Adicionar à tela inicial".
