# Checklist de Producao - Supabase + Render (WallFruits)

Este guia deixa o backend pronto para producao com Supabase Auth + Supabase Storage no Render.

## 1) Supabase

### 1.1 Banco (Postgres)
- Abra o projeto no Supabase.
- Copie a string de conexao PostgreSQL em: `Project Settings > Database > Connection string`.
- Use essa string no `DATABASE_URL` do Render.

### 1.2 Auth
- Garanta que o projeto tem Auth ativo.
- Copie:
  - `SUPABASE_URL`
  - `SUPABASE_ANON_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY`

### 1.3 Storage
- Crie um bucket publico (ex.: `wallfruits-media`).
- Use este nome em `SUPABASE_STORAGE_BUCKET`.
- Se usar CDN/custom domain, preencha `SUPABASE_STORAGE_PUBLIC_BASE_URL`.

## 2) Render (Web Service)

Defina estas variaveis de ambiente:

- `APP_ENV=production`
- `DEBUG=false`
- `SECURITY_ENFORCE_PRODUCTION_HARDENING=true`
- `DATABASE_URL=<postgres do supabase>`
- `SECRET_KEY=<chave forte>`
- `RATE_LIMIT_ENABLED=true`
- `JWT_ISSUER=<issuer esperado, ex: wallfruits-api>`
- `JWT_AUDIENCE=<audience esperada, ex: wallfruits-clients>`
- `JWT_REQUIRE_ISSUER=true`
- `JWT_REQUIRE_AUDIENCE=true`
- `AI_ENFORCE_SUBSCRIPTION_GUARDRAILS=true`
- `SUPABASE_AUTH_ENABLED=true`
- `SUPABASE_URL=<url do projeto supabase>`
- `SUPABASE_ANON_KEY=<anon key>`
- `SUPABASE_SERVICE_ROLE_KEY=<service role key>`
- `SUPABASE_STORAGE_ENABLED=true`
- `SUPABASE_STORAGE_BUCKET=<nome do bucket publico>`
- `SUPABASE_STORAGE_PUBLIC_BASE_URL=` (vazio se nao usar CDN propria)
- `SUPABASE_STORAGE_TIMEOUT_SECONDS=20`
- `REDIS_ENABLED=false` (ou `true` se preencher `REDIS_URL`)
- `REDIS_URL=<url do redis>` (somente quando REDIS_ENABLED=true)
- `STRIPE_PRICE_ENTERPRISE=<price_id mensal enterprise>`
- `STRIPE_PRICE_ENTERPRISE_YEARLY=<price_id anual enterprise>`
- `WEB_CONCURRENCY=1` (aumentar para 2 em plano com mais CPU/RAM)

## 3) Render (Worker Celery)

Defina as mesmas variaveis essenciais do backend:
- `APP_ENV=production`
- `DATABASE_URL`
- `SECRET_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `REDIS_ENABLED` e `REDIS_URL` (se usar)
- `OPENAI_API_KEY` (se usar IA)

## 4) Deploy

- Execute `Deploy latest` no Render.
- Aguarde o start (`alembic upgrade head` + uvicorn).

## 5) Validacao rapida

### 5.1 Endpoints
- `GET /` deve responder 200.
- `GET /docs` deve responder 200.
- `GET /health/live` deve responder 200.
- `GET /health/ready` deve responder 200 (se der 503, normalmente e DB/Redis/env faltando).

### 5.2 Storage smoke
Com as env vars setadas, rode:

- `python scripts/05_supabase_storage_smoke.py`

Esperado:
- `OK: upload/delete no Supabase Storage funcionou`

## 6) Publicacao Android (Play Store)

- Gere AAB assinado (`bundleRelease`).
- Use o workflow: `.github/workflows/build-android-aab-release.yml`.
- Configure os secrets de assinatura no GitHub:
  - `WF_KEYSTORE_BASE64`
  - `WF_KEYSTORE_PASSWORD`
  - `WF_KEY_ALIAS`
  - `WF_KEY_PASSWORD`

## 7) Erros comuns

- Health 503 com app abrindo: geralmente `REDIS_ENABLED=true` sem `REDIS_URL`.
- Erro de auth Supabase: chave errada ou faltando `SUPABASE_URL`.
- Upload falhando: bucket inexistente/privado ou `SUPABASE_SERVICE_ROLE_KEY` invalida.
