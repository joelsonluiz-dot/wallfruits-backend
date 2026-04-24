# Upgrade para Producao - Mobile Nativo + Web Desktop

## Objetivo
Transformar o produto para o modelo:
- Celular: apps nativos (Android Kotlin e iOS Swift)
- Web: apenas desktop

## O que ja foi aplicado
- Web mobile bloqueado no Nginx do desktop-web, com redirecionamento para pagina de orientacao.
- Regra de plataforma consolidada para manter Android em Kotlin, iOS em Swift e desktop em React/TypeScript.

## Arquivos alterados neste upgrade
- desktop-web/nginx.conf
- .github/copilot-instructions.md
- mobile_native/android-kotlin/README.md
- mobile_native/ios-swift/README.md
- desktop-web/public/mobile-app.html

## Fase 1 - Base de producao (imediata)
1. Publicar links oficiais das lojas:
   - Substituir URLs em desktop-web/public/mobile-app.html
2. Ajustar dominio web desktop:
   - Manter wallfruits.com.br para desktop web
3. Validar redirecionamento mobile:
   - Android Chrome e iOS Safari devem abrir /mobile-app.html via desktop-web/nginx.conf

## Fase 2 - Android nativo (Kotlin)
1. Criar app Android no Android Studio (Kotlin, minSdk 26+).
2. Arquitetura recomendada:
   - UI: Jetpack Compose
   - Estado: ViewModel + StateFlow
   - Rede: Retrofit + OkHttp
   - DI: Hilt
   - Persistencia: Room
3. Integracao backend:
   - Reusar APIs FastAPI existentes
   - JWT com refresh token
4. Release:
   - Gerar .aab
   - Publicar no Google Play (track interno, depois producao)

## Fase 3 - iOS nativo (Swift)
1. Criar app iOS no Xcode (SwiftUI, iOS 16+).
2. Arquitetura recomendada:
   - UI: SwiftUI
   - Estado: Observable / MVVM
   - Rede: URLSession + async/await
   - Persistencia: SwiftData ou CoreData
3. Integracao backend:
   - Mesmo contrato de API do Android
   - Keychain para token seguro
4. Release:
   - Archive + TestFlight
   - Publicar na App Store

## Fase 4 - Operacao de producao
1. Observabilidade:
   - Sentry para apps mobile
   - Logs e traces no backend
2. Seguranca:
   - Pinning de certificado (opcional avancado)
   - Hardening JWT ja habilitado no backend
3. CI/CD:
   - Android: GitHub Actions com build .aab
   - iOS: Xcode Cloud ou GitHub Actions macOS runner
4. Qualidade:
   - Smoke tests API
   - Testes de login, feed, publicacao e notificacoes
   - Smoke de politica web desktop/mobile via workflow dedicado

## CI/CD aplicado neste repositorio
1. Android release:
   - Workflow: .github/workflows/build-android-aab-release.yml
   - Build AAB e opcional publicacao em track do Google Play
2. iOS TestFlight (template):
   - Workflow: .github/workflows/ios-testflight-native.yml
   - Ativa quando o projeto Swift nativo estiver no repositorio
3. Validacao web desktop/mobile:
   - Script: scripts/08_smoke_web_desktop_mobile_policy.py
   - Workflow: .github/workflows/smoke-web-desktop-mobile-policy.yml
4. Readiness autonomo ponta-a-ponta:
   - Script: scripts/09_autonomous_production_readiness.py
   - Workflow: .github/workflows/autonomous-production-readiness.yml
   - Execucao local exemplo:
     - python scripts/09_autonomous_production_readiness.py --api-base-url https://wallfruits-api.onrender.com --web-base-url https://wallfruits.com.br

## Checklist de go-live
- [ ] Links de loja atualizados
- [ ] Android publicado (interno e producao)
- [ ] iOS publicado (TestFlight e producao)
- [ ] Web desktop validado em Chrome/Safari/Edge
- [ ] Web mobile redirecionando para pagina de app nativo
- [ ] Monitoramento e alertas ativos

## Observacao importante
A stack identica ao Instagram em alto nivel e mobile nativo por plataforma + web desktop, exatamente o modelo definido aqui.
