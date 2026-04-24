# APK Android (WallFruits)

Este repositório inclui um app Android nativo em Kotlin em `mobile_native/android-kotlin/WallFruitsAndroid`.

## O que o APK entrega

- Login JWT
- Home feed
- Navegação inferior
- Base de API em produção

## Como baixar APK

1. Abra a aba **Actions** no GitHub.
2. Execute o workflow **Build Android APK (Native Kotlin)**.
3. Ao finalizar, baixe o artefato `wallfruits-android-native-apk`.
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

- O starter nativo ainda precisa de assinatura configurada para release.
- Quando isso estiver pronto, o workflow [Build Android Release (AAB)](.github/workflows/build-android-aab-release.yml) usará secrets.

Secrets esperados no GitHub:
- `WF_KEYSTORE_BASE64` (keystore em base64)
- `WF_KEYSTORE_PASSWORD`
- `WF_KEY_ALIAS`
- `WF_KEY_PASSWORD`

### 3) Gerar AAB

Local:

- `gradle -p mobile_native/android-kotlin/WallFruitsAndroid bundleRelease`

O arquivo sai em:

- `mobile_native/android-kotlin/WallFruitsAndroid/app/build/outputs/bundle/release/app-release.aab`

### 4) Observação importante (política)

Este app é nativo em Kotlin, então a política da Play Store tende a ser mais favorável do que a de um wrapper WebView.
