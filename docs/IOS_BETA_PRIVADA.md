# Beta Privada iOS

## Objetivo
Testar o app WallFruits no proprio iPhone antes da publicacao publica.

## Requisitos
- Apple Developer Program ativo.
- Apple ID com acesso ao App Store Connect.
- Projeto iOS nativo gerado a partir de `mobile_native/ios-swift/WallFruitsiOS/project.yml`.

## Se voce so tem Windows 10
- Nao tente compilar o iOS localmente no Windows.
- O fluxo recomendado e: fazer push pelo VS Code, deixar o GitHub Actions gerar o projeto Xcode e enviar o build para TestFlight.
- Depois, no iPhone, instalar o app TestFlight e aceitar o build privado.

## Caminho mais simples sem Mac
1. Configure os secrets do App Store Connect no GitHub.
2. Faça push das mudanças para `main` no VS Code.
3. O workflow `.github/workflows/ios-testflight-native.yml` roda no macOS da GitHub Actions.
4. O workflow gera `WallFruitsiOS.xcodeproj` com XcodeGen.
5. O build e assinado com o `APPLE_TEAM_ID` e enviado para TestFlight.
6. No iPhone, abra o app TestFlight e instale a beta privada.

## Caminho recomendado para beta privada com TestFlight
1. Crie o app no App Store Connect usando o bundle id `com.wallfruits.app`.
2. Gere um archive do app pelo workflow `.github/workflows/ios-testflight-native.yml`.
3. Envie o build para o App Store Connect / TestFlight.
4. Em App Store Connect, abra `TestFlight`.
5. Adicione seu Apple ID em `Internal Testing` para liberar acesso privado.
6. Instale o app `TestFlight` no proprio iPhone.
7. Abra o convite interno ou o link do teste e instale o build.

## Inputs do workflow de TestFlight
- Nao ha inputs obrigatorios.
- O workflow gera o projeto Xcode automaticamente com XcodeGen.
- O workflow usa `APPLE_TEAM_ID` para assinatura automatica no CI.
- Secrets obrigatorios:
  - `APPLE_ISSUER_ID`
  - `APPLE_KEY_ID`
  - `APPLE_API_PRIVATE_KEY_BASE64`
  - `APPLE_TEAM_ID`
  - `IOS_BUNDLE_ID`

## Observacoes
- Beta privada nao exige publicacao na App Store.
- O iPhone precisa do app `TestFlight` apenas quando a distribuicao for por TestFlight.
- Em Windows nao e possivel compilar ou assinar o app iOS localmente; use o workflow no GitHub Actions para construir e distribuir.