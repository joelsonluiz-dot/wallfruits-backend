# QA Visual Checklist — WallFruits

Objetivo
- Confirmar que Web, Android e iOS exibem a mesma base visual e lógica principal.

Checklist
- [ ] Hero com mesmo tom, título e subtítulo na tela inicial.
- [ ] Mesmas cores principais: azul primário, laranja secundário, neutros e fundo claro.
- [ ] Mesma ordem visual: hero, métricas, ações, cards de feed.
- [ ] Mesma informação exibida nos cards: Sessão, Feed, Marketplace e IA.
- [ ] Mesmos textos de CTA: Atualizar e Sair.
- [ ] Mesmos raios de borda e padding aproximado em cards.
- [ ] Mesma hierarquia tipográfica entre título, subtítulo e metadados.
- [ ] Tema consistente em estados vazio/erro/carregando.
- [ ] Navegação e logout mantêm comportamento equivalente por plataforma.

Validação por plataforma
- Web: revisar em desktop responsivo e confirmar tokens em `desktop-web/src/styles/tokens.css`.
- Android: revisar `Theme.kt`, `UiTokens.kt` e `HomeScreen.kt`.
- iOS: revisar `Colors.swift` e `FeedView.swift`.

Notas
- Flutter fica fora do escopo desta entrega, conforme pedido.
- Backend Render continua como referência de versão e implantação.
