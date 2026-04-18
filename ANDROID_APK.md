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
- Para loja (Play Store), o próximo passo é gerar build **release** com assinatura e preferencialmente **AAB** (Android App Bundle).

## Play Store (Release / AAB)

### 1) Criar keystore (uma vez)

Você precisa de uma keystore de assinatura (NUNCA perder). Exemplo (local):

- Gerar: `keytool -genkeypair -v -keystore release.keystore -alias wallfruits -keyalg RSA -keysize 2048 -validity 10000`
- Guardar: senha do keystore + senha da chave + alias.

### 2) Configurar o projeto para assinar

- Exemplo: [android/keystore.properties.example](android/keystore.properties.example)
- Em produção/CI, o workflow [Build Android Release (AAB)](.github/workflows/build-android-aab-release.yml) usa secrets.

Secrets esperados no GitHub:
- `WF_KEYSTORE_BASE64` (keystore em base64)
- `WF_KEYSTORE_PASSWORD`
- `WF_KEY_ALIAS`
- `WF_KEY_PASSWORD`

### 3) Gerar AAB

Local:

- `gradle -p android bundleRelease`

O arquivo sai em:

- `android/app/build/outputs/bundle/release/app-release.aab`

### 4) Observação importante (política)

Este app é um wrapper WebView apontando para o site. Dependendo do conteúdo e da proposta, a Play Store pode rejeitar apps que são “apenas um site dentro de um app”.
Se isso virar um problema, o caminho mais aceito costuma ser publicar como **PWA via TWA (Trusted Web Activity)** ou evoluir para app nativo/Flutter.

## Experiência de app web (PWA)

Além do APK, o projeto também foi preparado como PWA:

- Manifest: `/static/manifest.webmanifest`
- Service Worker: `/static/sw.js`

No Android (Chrome), também é possível instalar via "Adicionar à tela inicial".
