# 🆓 Deploy GRÁTIS - Melhores Opções para FastAPI

## ⚠️ Por que NÃO usar Firebase para este projeto?

Firebase é ótimo para:
- ✅ Frontend (HTML/React/Vue)
- ✅ Autenticação
- ✅ NoSQL (Firestore)

**MAS não é ideal para:**
- ❌ FastAPI (Python web framework)
- ❌ PostgreSQL (banco relacional)
- ❌ APIs complexas com ORM

---

## 🏆 MELHORES OPÇÕES GRATUITAS (em ordem)

### 1️⃣ RENDER (MAIS FÁCIL - RECOMENDADO!)
- ✅ **100% Grátis**
- ✅ FastAPI nativo
- ✅ PostgreSQL incluído (1 GB)
- ✅ Deploy automático do Git
- ✅ HTTPS grátis
- ⏱️ Deploy em **5 minutos**

**Limitações:** API "dorme" após 15min sem uso (acorda em ~30s)

---

### 2️⃣ RAILWAY
- ✅ $5 de crédito grátis por mês
- ✅ FastAPI + PostgreSQL + Redis
- ✅ 500 horas grátis/mês
- ✅ Deploy do Git
- ✅ Muito rápido

**Limitações:** Depois de $5, precisa adicionar cartão

---

### 3️⃣ FLY.IO
- ✅ Plano gratuito generoso
- ✅ FastAPI + PostgreSQL
- ✅ Docker nativo
- ✅ Sempre ativo (não dorme)

**Limitações:** Mais técnico, pede cartão (não cobra)

---

### 4️⃣ PYTHONANYWHERE
- ✅ 100% Grátis
- ✅ Específico para Python
- ✅ MySQL grátis
- ✅ Sempre ativo

**Limitações:** Precisa adaptar de PostgreSQL para MySQL/SQLite

---

## 🚀 GUIA RÁPIDO: RENDER (Recomendado)

### PASSO 1: Preparar código no Git

**No PowerShell (seu PC):**
```powershell
cd C:\Users\User\Desktop\wallfruits-backend

# Inicializar Git (se ainda não fez)
git init
git add .
git commit -m "Deploy inicial Render"
git branch -M main

# Criar repositório no GitHub e push
# Vá em: https://github.com/new
# Nome: wallfruits-backend
# Público ou Privado (tanto faz)
# NÃO inicialize com README

git remote add origin https://github.com/SEU_USUARIO/wallfruits-backend.git
git push -u origin main
```

---

### PASSO 2: Criar conta Render

1. Acesse: https://render.com/
2. Clique "Get Started for Free"
3. Login com GitHub (mais fácil)
4. Autorize Render a acessar repositórios

---

### PASSO 3: Deploy PostgreSQL (Banco de Dados)

1. No Dashboard Render, clique "New +" → "PostgreSQL"
2. Configurações:
   - **Name**: `wallfruits-db`
   - **Database**: `wallfruits_db`
   - **User**: `wallfruits`
   - **Region**: Oregon (Free)
   - **PostgreSQL Version**: 16
   - **Plan**: Free
3. Clique "Create Database"
4. Aguarde 1-2 minutos
5. **Copie a "Internal Database URL"** (algo como `postgresql://user:pass@...`)

---

### PASSO 4: Deploy FastAPI (Web Service)

1. No Dashboard, clique "New +" → "Web Service"
2. Conecte seu repositório GitHub `wallfruits-backend`
3. Configurações:
   - **Name**: `wallfruits-api`
   - **Region**: Oregon (Free)
   - **Branch**: `main`
   - **Root Directory**: (deixe vazio)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free

4. **Environment Variables** (clique "Add Environment Variable"):

```
DATABASE_URL = cole_aqui_a_Internal_Database_URL_do_passo_3
SECRET_KEY = cole_uma_chave_forte_aqui
DEBUG = false
REDIS_ENABLED = false
CORS_ORIGINS = ["https://wallfruits-api.onrender.com"]
ALLOWED_HOSTS = ["wallfruits-api.onrender.com"]
```

**Gerar SECRET_KEY:**
```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

5. Clique "Create Web Service"

---

### PASSO 5: Aguardar deploy

- Render vai fazer build (2-5 minutos)
- Acompanhe os logs na tela
- Quando terminar, mostra "Live" 🟢

---

### PASSO 6: Testar

Seu site estará em:
```
https://wallfruits-api.onrender.com/health
https://wallfruits-api.onrender.com/docs
https://wallfruits-api.onrender.com/qa
```

---

## 🎯 GUIA RÁPIDO: RAILWAY

### PASSO 1: Código no Git (igual ao Render)

### PASSO 2: Criar conta Railway
1. https://railway.app/
2. Login com GitHub
3. Inicia com $5 grátis

### PASSO 3: New Project
1. Dashboard → "New Project"
2. "Deploy from GitHub repo"
3. Selecione `wallfruits-backend`

### PASSO 4: Adicionar PostgreSQL
1. Clique "New" → "Database" → "Add PostgreSQL"
2. Automaticamente conecta

### PASSO 5: Configurar variáveis
1. Selecione o serviço Python
2. Aba "Variables"
3. Adicione:

```
SECRET_KEY = gere_uma_chave_forte
REDIS_ENABLED = false
DEBUG = false
```

DATABASE_URL já é criada automaticamente!

### PASSO 6: Deploy automático
Railway detecta FastAPI e faz deploy automático!

URL final: `https://wallfruits-backend-production.up.railway.app`

---

## 📱 E se eu REALMENTE quiser Firebase?

Você pode usar Firebase **JUNTO** com outro serviço:

**Arquitetura híbrida:**
- **Firebase Hosting**: Frontend (HTML/React)
- **Firebase Auth**: Autenticação de usuários
- **Firebase Storage**: Upload de imagens
- **Render/Railway**: API FastAPI (backend)

Desta forma aproveita o melhor dos dois mundos!

---

## 💰 Comparação de custos

| Serviço | Custo | FastAPI | PostgreSQL | Sempre ativo |
|---------|-------|---------|------------|--------------|
| **Render** | Grátis | ✅ | ✅ 1GB | ❌ Dorme 15min |
| **Railway** | $5/mês grátis | ✅ | ✅ | ✅ Até acabar crédito |
| **Fly.io** | Grátis | ✅ | ✅ 3GB | ✅ |
| **Oracle Cloud** | Grátis sempre | ✅ Docker | ✅ Self-host | ✅ |
| **PythonAnywhere** | Grátis | ✅ | ⚠️ MySQL | ✅ |
| **Firebase Functions** | Grátis limitado | ⚠️ Serverless | ❌ | ⚠️ Por request |

---

## 🎖️ Minha recomendação para VOCÊ

**Opção 1 (Mais fácil):**
1. Deploy no **Render** agora (5 minutos)
2. Testar com usuários
3. Se precisar "sempre ativo", migra depois

**Opção 2 (Melhor grátis):**
1. **Oracle Cloud** (guia que criei antes)
2. 100% grátis para sempre
3. VM completa com 24 GB RAM

**Opção 3 (Meio termo):**
1. **Railway** ($5/mês grátis)
2. Muito fácil de usar
3. Quando acabar crédito, adiciona cartão ou migra

---

## 📋 Qual você quer tentar?

Responda:
1. **Render** - quero o mais fácil e rápido
2. **Railway** - quero facilidade + melhor performance
3. **Oracle Cloud** - quero grátis para sempre (mais técnico)
4. **Outra** - me explica mais detalhes

Eu crio o guia específico detalhado! 🚀
