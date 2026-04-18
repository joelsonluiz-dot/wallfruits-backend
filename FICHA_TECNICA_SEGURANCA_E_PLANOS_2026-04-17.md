# Ficha Tecnica - Seguranca, Planos e Operacao de IA (2026-04-17)

## 1. Objetivo

Esta entrega separa acesso de administracao da plataforma versus administracao de conta assinante, aplica guardrails por plano de assinatura nos fluxos de IA e reforca exigencias de producao para reduzir risco de fuga de rota e abuso de automacao.

## 2. Alteracoes de arquitetura

### 2.1 Modelo de acesso por dois eixos

No modelo de usuario agora existem tres campos de governanca:

- `platform_role`: controle interno da empresa/plataforma.
- `account_role`: controle do assinante dentro da sua conta.
- `account_scope_id`: escopo logico da conta (tenant).

Taxonomia:

- Platform: `none`, `staff_support`, `staff_ops`, `staff_admin`
- Conta: `account_viewer`, `account_analyst`, `account_manager`, `account_owner`

### 2.2 Guardrails de assinatura (IA)

A IA passa a considerar capacidades por plano:

- `allowed_autonomy_modes`
- `max_auto_execute_per_day`
- `allow_auto_negotiation`
- `allow_auto_flash_auction`
- `allow_business_os_marketing_loop`
- `allow_business_os_persist`

Planos suportados:

- `none`
- `basic`
- `pro`
- `premium`
- `enterprise`

### 2.3 Endurecimento de producao

Foi adicionado bloqueio de inicializacao para producao quando hardening obrigatorio nao estiver atendido.

## 3. Matriz resumida de acesso

### 3.1 Operacao interna da plataforma (rotas /ai administrativas)

- Leitura operacional: `staff_support`, `staff_ops`, `staff_admin`
- Escrita operacional (persistencia, orquestracao, resolucao de fila, aplicar policy): `staff_ops`, `staff_admin`

### 3.2 Operacao de conta assinante (agenda/autonomia)

- Leitura de perfil/capacidades: `account_viewer`+
- Atualizacao de perfil de autonomia: `account_manager` e `account_owner`
- Execucao de automacao comercial: `account_analyst`, `account_manager`, `account_owner`

Observacao: para execucao autonoma em modo commit, aplica-se limite diario por plano.

## 4. Capacidades por plano (resumo)

- `none/basic`: modo assistido, sem execucao autonoma commit.
- `pro`: assistida + semi_autonoma, auto negociacao habilitada, limite diario reduzido.
- `premium`: inclui modo autonoma, leilao relampago e limites mais altos.
- `enterprise`: mesmo conjunto premium com teto diario ampliado.

## 5. Variaveis de ambiente de producao (obrigatorias)

Quando `APP_ENV=production` e `SECURITY_ENFORCE_PRODUCTION_HARDENING=true`:

- `DEBUG=false`
- `RATE_LIMIT_ENABLED=true`
- `JWT_REQUIRE_ISSUER=true`
- `JWT_REQUIRE_AUDIENCE=true`
- `JWT_ISSUER=<issuer esperado>`
- `JWT_AUDIENCE=<audience esperada>`
- `AI_ENFORCE_SUBSCRIPTION_GUARDRAILS=true`

Para plano enterprise no Stripe:

- `STRIPE_PRICE_ENTERPRISE=<price_id mensal>`
- `STRIPE_PRICE_ENTERPRISE_YEARLY=<price_id anual>`

## 6. Compatibilidade e migracao de dados

- Foi adicionada migration Alembic para incluir as colunas novas em `users`.
- Usuarios legados com `role=admin` sao promovidos para `platform_role=staff_admin` na migration.
- Validacoes legadas continuam com fallback para reduzir quebra durante transicao.

## 7. Checklist rapido de deploy

1. Aplicar migration: `alembic upgrade head`
2. Confirmar env vars de hardening/JWT/IA
3. Validar login e claims JWT (`iss`/`aud`)
4. Validar acesso por perfis de plataforma e conta
5. Validar limites diarios de execucao autonoma
6. Validar checkout/planos com enterprise
