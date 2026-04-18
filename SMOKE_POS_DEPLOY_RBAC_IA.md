# Smoke Pos-Deploy RBAC + IA (Producao)

## 1) Objetivo

Validar rapidamente em producao:

- Separacao de permissao entre leitura e escrita de operacao interna da plataforma.
- Isolamento entre papeis da conta assinante.
- Guardrails de assinatura para autonomia da IA.

## 2) Pre-requisitos

- API publicada e saudavel.
- Migration aplicada: `alembic upgrade head`.
- Variaveis de hardening em producao configuradas.
- Tokens JWT validos para perfis diferentes.

Execucao recomendada da migration no ambiente alvo (Render Shell):

```bash
python -m alembic upgrade head
```

Perfis sugeridos:

- `TOKEN_PLATFORM_SUPPORT` (staff_support)
- `TOKEN_PLATFORM_OPS` (staff_ops)
- `TOKEN_ACCOUNT_VIEWER` (account_viewer)
- `TOKEN_ACCOUNT_MANAGER` (account_manager)
- `TOKEN_ACCOUNT_ANALYST` (account_analyst)

Defina:

```powershell
$BASE = "https://SEU-SERVICO.onrender.com"
$TOKEN_PLATFORM_SUPPORT = "..."
$TOKEN_PLATFORM_OPS = "..."
$TOKEN_ACCOUNT_VIEWER = "..."
$TOKEN_ACCOUNT_MANAGER = "..."
$TOKEN_ACCOUNT_ANALYST = "..."
```

## 2.1) Execucao automatizada (recomendado)

Opcao A, passando tokens por argumento:

```powershell
python scripts/06_smoke_rbac_ai.py --base-url "$BASE" --strict-ready --analyst-expected-status 200_or_403 --token-platform-support "$TOKEN_PLATFORM_SUPPORT" --token-platform-ops "$TOKEN_PLATFORM_OPS" --token-account-viewer "$TOKEN_ACCOUNT_VIEWER" --token-account-manager "$TOKEN_ACCOUNT_MANAGER" --token-account-analyst "$TOKEN_ACCOUNT_ANALYST"
```

Opcao B, usando variaveis de ambiente:

```powershell
$env:WF_TOKEN_PLATFORM_SUPPORT = $TOKEN_PLATFORM_SUPPORT
$env:WF_TOKEN_PLATFORM_OPS = $TOKEN_PLATFORM_OPS
$env:WF_TOKEN_ACCOUNT_VIEWER = $TOKEN_ACCOUNT_VIEWER
$env:WF_TOKEN_ACCOUNT_MANAGER = $TOKEN_ACCOUNT_MANAGER
$env:WF_TOKEN_ACCOUNT_ANALYST = $TOKEN_ACCOUNT_ANALYST

python scripts/06_smoke_rbac_ai.py --base-url "$BASE" --strict-ready --analyst-expected-status 200_or_403
```

## 2.2) Execucao via GitHub Actions (pos-deploy)

Workflow:

- `.github/workflows/smoke-rbac-ai-post-deploy.yml`

Disparos configurados:

- Automatico em `deployment_status` com estado `success`.
- Manual em `workflow_dispatch`.

Secrets esperados no repositorio:

- `WF_TOKEN_PLATFORM_SUPPORT`
- `WF_TOKEN_PLATFORM_OPS`
- `WF_TOKEN_ACCOUNT_VIEWER`
- `WF_TOKEN_ACCOUNT_MANAGER`
- `WF_TOKEN_ACCOUNT_ANALYST`

URL base da API para o workflow:

- Preferencia 1: `workflow_dispatch` input `base_url`
- Preferencia 2: `deployment_status.environment_url`
- Preferencia 3: repository variable `WF_SMOKE_BASE_URL`
- Preferencia 4: secret `WF_SMOKE_BASE_URL`

## 3) Health basico

```powershell
curl "$BASE/health/live"
curl "$BASE/health/ready"
curl "$BASE/api/metrics"
```

Esperado:

- `/health/live` -> `200`
- `/health/ready` -> `200`
- `/api/metrics` -> `200`

## 4) Operacao interna da plataforma (read vs write)

### 4.1 Leitura operacional permitida para support

```powershell
curl -H "Authorization: Bearer $TOKEN_PLATFORM_SUPPORT" "$BASE/api/ai/ops/governance-summary?days=7"
```

Esperado:

- `200`

### 4.2 Escrita operacional bloqueada para support

```powershell
curl -H "Authorization: Bearer $TOKEN_PLATFORM_SUPPORT" "$BASE/api/ai/ops/business-os/marketing-funnel?days=7&min_segment_signals=3&persist=true"
```

Esperado:

- `403`

### 4.3 Escrita operacional permitida para ops

```powershell
curl -H "Authorization: Bearer $TOKEN_PLATFORM_OPS" "$BASE/api/ai/ops/business-os/marketing-funnel?days=7&min_segment_signals=3&persist=true"
```

Esperado:

- `200`

## 5) Operacao da conta assinante

### 5.1 Viewer pode ler perfil de agenda

```powershell
curl -H "Authorization: Bearer $TOKEN_ACCOUNT_VIEWER" "$BASE/api/ai/agenda/profile"
```

Esperado:

- `200`
- Corpo com `subscription_capabilities`

### 5.2 Viewer nao pode alterar perfil de autonomia

```powershell
$bodyViewer = @{
  autonomy_mode = "assistida"
  main_goal = "produtividade"
  decision_style = "equilibrado"
  preferred_contact_period = "manha"
  guardrail_max_discount_pct = 8
  guardrail_min_net_margin_pct = 7
  guardrail_max_response_hours = 12
  guardrail_risk_tolerance = "medio"
  flash_auction_window_minutes = 90
  flash_spoilage_risk_threshold = 62
  auto_execute_limit_per_day = 0
} | ConvertTo-Json

curl -Method Post -ContentType "application/json" -Body $bodyViewer -H "Authorization: Bearer $TOKEN_ACCOUNT_VIEWER" "$BASE/api/ai/agenda/profile"
```

Esperado:

- `403`

### 5.3 Manager pode alterar perfil em modo permitido pelo plano

```powershell
$bodyManager = @{
  autonomy_mode = "assistida"
  main_goal = "margem"
  decision_style = "equilibrado"
  preferred_contact_period = "manha"
  guardrail_max_discount_pct = 8
  guardrail_min_net_margin_pct = 7
  guardrail_max_response_hours = 12
  guardrail_risk_tolerance = "medio"
  flash_auction_window_minutes = 90
  flash_spoilage_risk_threshold = 62
  auto_execute_limit_per_day = 0
} | ConvertTo-Json

curl -Method Post -ContentType "application/json" -Body $bodyManager -H "Authorization: Bearer $TOKEN_ACCOUNT_MANAGER" "$BASE/api/ai/agenda/profile"
```

Esperado:

- `200`

### 5.4 Analyst acessa plano autonomo conforme assinatura

```powershell
curl -H "Authorization: Bearer $TOKEN_ACCOUNT_ANALYST" "$BASE/api/ai/agenda/autonomous-commerce"
```

Esperado:

- `200` se plano for `pro` ou superior
- `403` se plano nao habilitar recurso

## 6) Criterio de aprovacao

A release passa no smoke quando:

1. Health basico ok.
2. Platform read/write separado corretamente.
3. Conta viewer sem permissao de escrita.
4. Conta manager com permissao de escrita compatível.
5. Guardrail por plano efetivo em autonomia.

## 7) Rollback rapido (se falhar)

1. Desabilitar trafego para build atual no Render.
2. Restaurar release anterior no Render.
3. Revisar env vars de hardening/JWT/IA.
4. Reexecutar smoke antes de reabrir trafego.
