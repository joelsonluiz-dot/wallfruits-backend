# Android Nativo (Kotlin) - Inicio rapido

## Stack alvo
- Kotlin
- Jetpack Compose
- Hilt
- Retrofit + OkHttp
- Room
- Coroutines + StateFlow

## Passos
1. Criar projeto no Android Studio:
   - Nome: WallFruitsAndroid
   - Linguagem: Kotlin
   - UI: Empty Compose Activity
2. Configurar flavors:
   - dev, staging, prod
3. Configurar base URL por flavor:
   - prod -> API publica de producao
4. Implementar modulos:
   - auth
   - feed
   - marketplace
   - ai-lab

## Padrao de pacote recomendado
com.wallfruits.app
- core
- data
- domain
- feature_auth
- feature_feed
- feature_market
- feature_ai

## Primeiro marco de producao
- Login JWT
- Feed principal
- Navegacao inferior
- Publicacao de conteudo
