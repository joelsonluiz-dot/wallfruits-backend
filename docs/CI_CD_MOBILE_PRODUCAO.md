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
2. O `project.yml` do starter deve gerar o `.xcodeproj` automaticamente via XcodeGen.
3. Assinaturas configuradas no App Store Connect.

## iOS - Como executar
1. Abrir Actions -> iOS Native TestFlight
2. Ou fazer push em `main` a partir do VS Code.
3. Validar upload no App Store Connect/TestFlight.

## iOS - Beta privada no proprio iPhone
- Use o guia em [IOS_BETA_PRIVADA.md](IOS_BETA_PRIVADA.md) para testar no seu aparelho sem publicar na App Store.
- Para beta privada com outras pessoas, adicione testers internos no App Store Connect e distribua via TestFlight.

## Validacao final de producao
- Android instala e autentica
- iOS instala via TestFlight e autentica
- Mobile web redireciona para pagina de app nativo
- Web desktop permanece operacional
