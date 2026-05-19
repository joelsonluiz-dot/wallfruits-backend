Plano de Unificação UI/UX — WallFruits

Objetivo
- Garantir aparência, cores, navegação, fluxo e lógica idênticos em Android, iOS e Web Desktop.

Escopo
- Design tokens: cores, tipografia, espaçamentos, raios, sombras, ícones.
- Componentes compartilhados: botões, inputs, cards, abas, navbar, headers, listas, modais.
- Temas: light/dark e variações de marca.
- Integração técnica: como consumir tokens em cada plataforma (CSS vars, Compose Theme, SwiftUI Assets, Flutter Theme).
- Rollout e QA: testes visuais e checklist de consistência.

Etapas (alto nível)
1. Definir tokens de design
   - Paleta principal (primária, secundária, sucesso, erro, aviso, neutros)
   - Tipografia (familia, pesos, tamanhos para H1..H6, body, caption)
   - Espaçamentos e escala (unit 4/8/16px)
   - Border radius e sombras
   - Iconografia (set padrão + tamanhos)

2. Criar artefatos compartilhados
   - `design/tokens.json` (JSON canonical com nomes e valores)
   - Geradores simples para cada plataforma (script que exporta CSS vars, XML para Android, XCAssets/Colors for iOS, Dart constants para Flutter)

3. Implementar temas base nas plataformas
   - Web: variáveis CSS + classes utilitárias + component library (React)
   - Android: Compose Theme usando tokens gerados
   - iOS: SwiftUI Color assets + Theme provider (ObservableObject)
   - Flutter: ThemeData a partir dos tokens gerados

4. Componentes compartilhados (prioridade)
   - Botão primário/secondary
   - AppBar / Bottom Tabs
   - Card de conteúdo / Lista de itens
   - Inputs e formulários

5. Testes e validação
   - Testes visuais (perceptual diff) entre plataformas para telas críticas
   - Checklist de UX (cores, texto, espaçamento, comportamento de navegação)

6. Rollout
   - Implementar em branch `ui-unify/2.0.0`
   - Revisões de PR e QA manual por plataforma
   - Release coordenado: publicar backend e web, depois mobile builds

Entregáveis
- `docs/UI_UX_UNIFICATION_PLAN.md` (este documento)
- `design/tokens.json` + scripts de export
- PRs com implementações por plataforma
- Checklist de QA

Recomendações rápidas
- Começar pelos tokens e por 3 telas: Feed, Perfil, Postagem (alta visibilidade).
- Usar um único arquivo `tokens.json` como fonte de verdade.
- Marcar versões de release sincronizadas (já alinhado para `2.0.0`).
