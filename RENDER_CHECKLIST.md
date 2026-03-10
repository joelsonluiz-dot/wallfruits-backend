# 🚀 Deploy no Render - Checklist Rápido

## ✅ 1. Prepare as Credenciais do Supabase (5 minutos)

Abra: https://supabase.com/dashboard

### 📍 De Settings → Database:
```
DATABASE_URL = postgresql://postgres.xxxxx:SENHA@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
SUPABASE_URL = https://seu-projeto.supabase.co
```

### 📍 De Settings → API:
```
SUPABASE_ANON_KEY = eyJhbGc... (a anon public)
SUPABASE_SERVICE_ROLE_KEY = eyJhbGc... (a service_role secret)
```

## ✅ 2. Configure no Render (10 minutos)

Abra: https://dashboard.render.com → Clique em **wallfruits-api**

### Abra aba "Environment" e adicione estas 7 variáveis:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | Cole a URL do PostgreSQL |
| `SUPABASE_URL` | https://seu-projeto.supabase.co |
| `SUPABASE_ANON_KEY` | Cole a anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Cole a service role key |
| `SUPABASE_AUTH_ENABLED` | true |
| `DEBUG` | false |
| `REDIS_ENABLED` | false |

**Clique: "Save Changes"**

## ✅ 3. Faça Deploy (5-7 minutos)

1. Clique em **"Manual Deploy"** (ou "Deploy")
2. Selecione **"Deploy latest commit"**
3. Aguarde o build terminar (status fica verde "Live")

## ✅ 4. Teste (1 minuto)

Abra no navegador:
- `https://wallfruits-api.onrender.com/health`
- `https://wallfruits-api.onrender.com/docs`

Se ambas funcionarem → **🎉 Pronto!**

---

## 📚 Mais Detalhes

Para um guia visual passo a passo, abra:
```
RENDER_DEPLOY_VISUAL.html
```

---

## ⚠️ Problemas Comuns

| Erro | Solução |
|------|---------|
| `ConnectionError` no banco | Verifique DATABASE_URL com ?sslmode=require |
| `unauthorized` auth | Confira SUPABASE_ANON_KEY |
| `/docs` carrega vazio | Ctrl+F5 ou abra em modo anônimo |
| Build falha | Cheque os logs no Render - pode ser erro Python |

---

**Tempo total: ~25 minutos** ⏱️

Se tiver dúvidas, o Render mostra os logs completos no painel - procure por mensagens de erro lá.
