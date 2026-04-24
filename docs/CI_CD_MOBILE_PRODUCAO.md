# CI/CD Mobile Producao

## Objetivo
Automatizar build e distribuicao de apps mobile no padrao nativo:
- Android: AAB com opcao de publicacao no Google Play
- iOS: IPA com upload para TestFlight (template)

## Workflows
- .github/workflows/build-android-aab-release.yml
- .github/workflows/ios-testflight-native.yml

## Android - Secrets obrigatorios
- WF_KEYSTORE_BASE64
- WF_KEYSTORE_PASSWORD
- WF_KEY_ALIAS
- WF_KEY_PASSWORD

## Android - Secrets para publicar no Google Play
- GOOGLE_PLAY_SERVICE_ACCOUNT_JSON
- GOOGLE_PLAY_PACKAGE_NAME

## Android - Como executar
1. Abrir Actions -> Build Android Release (AAB)
2. Selecionar:
   - upload_to_play = true ou false
   - play_track = internal/alpha/beta/production
3. Baixar artifact ou validar release no Play Console

## iOS - Secrets obrigatorios
- APPLE_ISSUER_ID
- APPLE_KEY_ID
- APPLE_API_PRIVATE_KEY_BASE64
- APPLE_TEAM_ID
- IOS_BUNDLE_ID

## iOS - Precondicoes
1. Projeto iOS nativo existente no repositorio.
2. Caminho do .xcodeproj informado no workflow dispatch.
3. Scheme de build existente e assinaturas configuradas.

## iOS - Como executar
1. Abrir Actions -> iOS Native TestFlight (Template)
2. Informar:
   - app_project_path
   - app_scheme
3. Executar e validar upload no App Store Connect/TestFlight

## Validacao final de producao
- Android instala e autentica
- iOS instala via TestFlight e autentica
- Mobile web redireciona para pagina de app nativo
- Web desktop permanece operacional
