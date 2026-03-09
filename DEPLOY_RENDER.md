# 🚀 Deploy no Render - Guia Completo

## ✅ Código já está preparado!

Arquivos prontos para Render:
- ✅ `requirements.txt` - dependências Python
- ✅ `render.yaml` - configuração automática
- ✅ `render.supabase.yaml` - configuração para API no Render + banco/auth no Supabase
- ✅ `.gitignore` - arquivos ignorados no Git
- ✅ `.env.example` - exemplo de variáveis

Se você for usar Supabase para banco e autenticação, prefira o blueprint `render.supabase.yaml`.

---

## 📍 PASSO 1: Enviar código para GitHub

### 1.1 Criar repositório no GitHub
1. Abra: https://github.com/new
2. Nome do repositório: `wallfruits-backend`
3. Descrição: `Marketplace de frutas FastAPI`
4. Visibilidade: **Privado** ou **Público** (tanto faz)
5. **NÃO** marque "Add README"
6. Clique "Create repository"

### 1.2 Copiar comandos que aparecem na tela

Você vai ver comandos assim:
```bash
git remote add origin https://github.com/SEU_USUARIO/wallfruits-backend.git
git branch -M main
git push -u origin main
```

**VOLTE AQUI NO VS CODE e execute no terminal integrado (Ctrl+`):**

```powershell
# Já inicializei o Git e fiz commit dos arquivos prontos
# Agora você só precisa adicionar o remote e fazer push

# Cole o comando que copiou do GitHub (troque SEU_USUARIO):
git remote add origin https://github.com/SEU_USUARIO/wallfruits-backend.git

# Enviar código:
git push -u origin main
```

Se pedir login:
- Username: seu usuario do GitHub
- Password: use um **Personal Access Token** (não a senha)
  - Gere em: https://github.com/settings/tokens
  - Gere → classic → repo (marcar) → Generate

---

## 📍 PASSO 2: Criar conta no Render

1. Acesse: https://render.com/
2. Clique "Get Started for Free"
3. Escolha "Sign up with GitHub" (mais fácil)
4. Autorize Render a acessar seus repositórios
5. Confirme email se pedir

---

## 📍 PASSO 3: Deploy do Blueprint (Automático!)

### Opção A: Com render.yaml (RECOMENDADO - 1 clique)

1. No Dashboard do Render, clique "New +"
2. Selecione "Blueprint"
3. Conecte seu repositório `wallfruits-backend`
4. Render detecta automaticamente o `render.yaml`
5. Clique "Apply"
6. Aguarde 3-5 minutos (acompanhe logs)

**Pronto! Render cria automaticamente:**
- ✅ Banco PostgreSQL
- ✅ Web Service FastAPI
- ✅ Configura variáveis de ambiente
- ✅ Gera SECRET_KEY automática

---

### Opção B: Manual (se render.yaml não funcionar)

#### 3.1 Criar PostgreSQL

1. Dashboard → "New +" → "PostgreSQL"
2. Configurações:
   - Name: `wallfruits-db`
   - Database: `wallfruits_db`
   - User: `wallfruits`
   - Region: **Oregon (Free)**
   - PostgreSQL Version: **16**
   - Plan: **Free**
3. Clique "Create Database"
4. Aguarde 1-2 minutos
5. Quando terminar, clique no banco criado
6. Role até "Connections"
7. **COPIE** a "Internal Database URL" (começa com `postgresql://`)

#### 3.2 Criar Web Service

1. Dashboard → "New +" → "Web Service"
2. Conecte repositório `wallfruits-backend`
3. Configurações:
   - **Name**: `wallfruits-api`
   - **Region**: Oregon (Free)
   - **Branch**: `main`
   - **Root Directory**: (deixe vazio)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: **Free**

4. Clique em "Advanced" → "Add Environment Variable"

**Adicione estas variáveis:**

```
DATABASE_URL
Cole aqui a Internal Database URL que você copiou
Exemplo: postgresql://wallfruits:senha@dpg-xxx.oregon-postgres.render.com/wallfruits_db

SECRET_KEY
Gere no terminal: python -c "import secrets; print(secrets.token_urlsafe(50))"

DEBUG
false

REDIS_ENABLED
false

ALGORITHM
HS256

ACCESS_TOKEN_EXPIRE_MINUTES
60

API_TITLE
WallFruits API

API_VERSION
2.0.0

CORS_ORIGINS
["https://wallfruits-api.onrender.com"]

ALLOWED_HOSTS
["wallfruits-api.onrender.com"]
```

**IMPORTANTE:** Nos últimos dois, troque `wallfruits-api` pelo nome que você escolheu.

5. Clique "Create Web Service"

---

## 📍 PASSO 4: Acompanhar Deploy

1. Render vai começar o build
2. Acompanhe os logs em tempo real
3. Procure por:
   - ✅ `Installing dependencies...`
   - ✅ `Starting service...`
   - ✅ `Application startup complete`
   - 🟢 Status muda para "Live"

Tempo total: **3-5 minutos**

---

## 📍 PASSO 5: Testar API

Sua API estará disponível em:
```
https://wallfruits-api.onrender.com
```

**Teste nos endpoints:**

1. **Health Check:**
```
https://wallfruits-api.onrender.com/health
```

Deve retornar:
```json
{
  "status": "ok",
  "version": "2.0.0",
  "environment": "production"
}
```

2. **Documentação interativa:**
```
https://wallfruits-api.onrender.com/docs
```

3. **Interface de testes:**
```
https://wallfruits-api.onrender.com/qa
```

---

## 🔄 Atualizar código depois

**Qualquer commit no GitHub atualiza automaticamente!**

```powershell
# No VS Code, faça alterações...

# Depois:
git add .
git commit -m "Atualizacao de features"
git push

# Render detecta e faz deploy automático!
```

---

## ⚙️ Ajustar variáveis depois

1. Dashboard Render
2. Clique no serviço `wallfruits-api`
3. Menu lateral → "Environment"
4. Edite variáveis
5. Clique "Save Changes"
6. Render reinicia automaticamente

---

## 📊 Logs e Monitoramento

**Ver logs:**
1. Dashboard → Seu serviço
2. Aba "Logs"
3. Logs em tempo real

**Ver métricas:**
1. Aba "Metrics"
2. CPU, Memória, Requisições

---

## ⚠️ Limitações do Plano Free

- ✅ **HTTPS** automático
- ✅ **Deploy contínuo** (git push = deploy)
- ✅ **PostgreSQL 1 GB**
- ✅ **Logs** completos
- ⚠️ API **"dorme"** após **15 minutos** sem requisições
- ⚠️ **Acorda** em ~30 segundos na primeira request
- ⚠️ **750 horas/mês** (suficiente para uso normal)

**Como evitar "sleep":**
- Use cron job para fazer ping a cada 10 min (gratuito)
- OU upgrade para plano pago ($7/mês)

---

## 🎯 Conectar com Frontend

Se você fizer um frontend (React/HTML), configure:

**Frontend:**
```javascript
const API_URL = "https://wallfruits-api.onrender.com"

fetch(`${API_URL}/health`)
  .then(res => res.json())
  .then(data => console.log(data))
```

**Ajustar CORS no Render:**
1. Environment Variables
2. Edite `CORS_ORIGINS`
3. Adicione seu domínio frontend:
```
["https://meu-frontend.vercel.app","https://wallfruits-api.onrender.com"]
```

---

## 🆘 Troubleshooting

### Build falhou
```
ERROR: Could not find requirements.txt
```
**Solução:** Certifique-se que o arquivo está na raiz do repositório

### Erro de porta
```
Error binding to port
```
**Solução:** Use `$PORT` no comando:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Banco não conecta
```
Connection refused (database)
```
**Solução:**
1. Use Internal Database URL (não External)
2. Formato: `postgresql://user:pass@host.oregon-postgres.render.com/db`

### Import Error
```
ModuleNotFoundError: No module named 'xxx'
```
**Solução:** Adicione o pacote em `requirements.txt` e faça push

---

## ✅ Checklist Final

- [ ] Código enviado para GitHub
- [ ] Conta Render criada com GitHub
- [ ] PostgreSQL criado (ou Blueprint aplicado)
- [ ] Web Service criado
- [ ] Variáveis de ambiente configuradas
- [ ] Deploy concluído (status "Live")
- [ ] `/health` retorna OK
- [ ] `/docs` acessível
- [ ] `/qa` funcionando

**Pronto! API no ar para usuários testarem! 🎉**

---

## 💡 Dicas extras

**Custom Domain (domínio próprio):**
1. Compre domínio (Registro.br, Namecheap)
2. Render → Settings → Custom Domain
3. Configure DNS conforme instruções

**Backup do banco:**
Render Free não tem backup automático. Faça manual:
1. Dashboard → Database → Connect
2. Use comando: `pg_dump`

**Monitorar uptime:**
- Use UptimeRobot (grátis)
- Ping a cada 5 minutos
- Mantém API acordada

---

Precisa de ajuda? Volte aqui! 🚀
