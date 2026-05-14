# WallFruits Desktop Web

## Stack
- React
- TypeScript
- Vite
- Static hosting via Render

## Objetivo
Esta é a web oficial para desktop. No celular, o usuário é redirecionado para a página do app nativo.

## Distribuição
- O CTA oficial para o APK Android aponta para o release `android-latest`.
- O desktop deve ser publicado como site estático no Render.

## Observação sobre responsividade
Foi aplicada uma correção em `src/styles.css` para melhorar a experiência em dispositivos móveis:
- Grade em duas colunas em telas pequenas (evita cards gigantes)
- Evita overflow de textos e imagens dentro de cards
- Melhora o comportamento de filtros e botões em telas estreitas

## Como rodar localmente
```bash
npm install
npm run dev
```

## Como buildar (produção)
```bash
cd desktop-web
npm install
npm run build
```

Se o seu ambiente de CI definir `NODE_ENV=production` e não instalar `devDependencies`, execute:
```bash
npm install --include=dev
npm run build
```

O artefato estará em `dist/` (conforme `vite.config.ts`).

## Notas de diagnóstico
- Se `npm run build` falhar dizendo que `tsc` não foi encontrado, o script de build foi ajustado para usar apenas `vite build` — ainda assim, verifique que `node_modules` está corretamente instalado.

## Próximos passos sugeridos
- Rodar `npm install` e `npm run build` no ambiente de build (eu também posso tentar novamente aqui se autorizar).
- Comitar as alterações e criar um PR com o changelog.
- Configurar CI (Render/Netlify) para publicar o site a partir da pasta `dist`.

