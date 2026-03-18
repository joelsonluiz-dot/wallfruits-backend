# 📋 Guia de Configuração e Limpeza - WallFruits

## 🚨 Status Atual

A aplicação está em erro por **autenticação falha com o Supabase**:
- ❌ DATABASE_URL está com senha expirada/incorreta
- ⚠️ SUPABASE_ANON_KEY não configurada

---

## ✅ Próximos Passos (em ordem)

### 1️⃣ Atualizar DATABASE_URL

**Origem:** Painel Supabase → Seu Projeto → Connect → PostgreSQL

```bash
# Execute o script de atualização interativo:
python scripts/00_update_database_url.py
```

**Onde colocar a nova senha:**
- Confirme se o script validou a conexão com sucesso ✓
- Atualize também no painel **Render** → Environment Variables

---

### 2️⃣ Limpar Todos os Dados de Usuários

**O script apaga em ordem respeitando Foreign Keys:**

```bash
# Limpa todos usuários, ofertas, negociações, logins, etc.
python scripts/01_clear_all_user_data.py
```

**Tabelas deletadas:**
- users, profiles, offers, negotiations, messages
- wallets, transactions, reviews, notifications
- auth_tokens, intermediation_requests, contracts
- E todas as dependências

---

### 3️⃣ Criar Conta Admin

**Gera conta de administrador com credenciais iniciais:**

```bash
python scripts/02_create_admin_account.py
```

**Credenciais que serão criadas:**
```
📧 Email: admin@wallfruits.com.br
🔐 Senha: Admin@2026Wallfruits
📱 Telefone: +55 (62) 98888-0001
⭐ Role: admin (superuser)
```

⚠️ **Mude a senha após o primeiro login!**

---

## 🤖 Botão Flutuante IA

### ✅ Já implementado em:
- **base.html** →incluído via `{% include 'components/ai_agent_button.html' %}`
- Irá aparecer em **todas as páginas** automaticamente

### Características:
- 🟣 Botão gradiente roxo flutuante (canto inferior direito)
- 📱 Responsivo em celular, tablet e desktop
- ⌨️ Fecha com ESC
- 🎯 Clica fora também fecha
- ✨ Animações suaves e pulso

### Configurar URL do Agente:
Edite [templates/components/ai_agent_button.html](../templates/components/ai_agent_button.html#L153):

```html
<!-- Descomente e altere a URL conforme necessário: -->
<iframe class="ai-agent-iframe" src="/ai-agent/" title="Agente IA WallFruits"></iframe>
```

---

## 📊 Ordem de Execução Recomendada

```
1. ✅ python scripts/00_update_database_url.py
   ↓
2. ✅ Reiniciar aplicação (local + Render)
   ↓
3. ✅ python scripts/01_clear_all_user_data.py
   ↓
4. ✅ python scripts/02_create_admin_account.py
   ↓
5. ✅ Login com admin@wallfruits.com.br / Admin@2026Wallfruits
   ↓
6. ✅ Aplicação pronta para uso!
```

---

## 🔐 Variáveis de Ambiente Necessárias

### Mínimo para funcionar:
```env
DATABASE_URL=postgresql://user:password@host:port/db
SECRET_KEY=sua_chave_secreta_aqui
```

### Completo (recomendado):
```env
# Bank
DATABASE_URL=postgresql://...
DB_ECHO=false

# JWT
SECRET_KEY=wallfruits_local_dev_secret_change_me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Supabase Auth (opcional)
SUPABASE_AUTH_ENABLED=false
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Email (opcional)
RESEND_API_KEY=
EMAIL_ENABLED=false

# Pagamentos (opcional)
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
```

---

## 🧪 Testes Após Configuração

```bash
# 1. Iniciar aplikação local
python -m uvicorn app.main:app --reload

# 2. Testar login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@wallfruits.com.br","password":"Admin@2026Wallfruits"}'

# 3. Verificar token
# Deve retornar access_token e user info
```

---

## 📂 Arquivos Criados

```
scripts/
  ├── 00_update_database_url.py      → Atualizar credenciais
  ├── 01_clear_all_user_data.py      → Limpar dados
  └── 02_create_admin_account.py     → Criar admin

templates/components/
  └── ai_agent_button.html           → Botão flutuante (novo)

templates/
  └── base.html                       → Incluído botão IA
```

---

## 🚀 Deploy no Render

```bash
# 1. Atualizar DATABASE_URL lá também
Render Dashboard → Variables → DATABASE_URL

# 2. Reiniciar aplicação
Render Dashboard → Redeployments → Deploy Latest

# 3. Executar scripts (SSH opcional)
# ou via API endpoint admin
```

---

## ❓ Problemas Comuns

### "password authentication failed"
→ DATABASE_URL está com senha errada  
→ Execute: `python scripts/00_update_database_url.py`

### "Admin criado mas não consigo logar"
→ Limpe cache do navegador (Ctrl+Shift+Del)  
→ Verifique se SECRET_KEY é consistente

### "Botão IA não aparece"
→ Verifique se base.html foi atualizado  
→ Limpe cache estático (Ctrl+F5)

---

## 📞 Suporte

**Documentação de Referência:**
- [WALLFRUITS_AGRO_V1_FOUNDATION.md](../WALLFRUITS_AGRO_V1_FOUNDATION.md)
- [ANDROID_APK.md](../ANDROID_APK.md)
- `app/core/config.py` → Configurações completas

**Contato:** admin@wallfruits.com.br

---

**Data: 17 de Março de 2026**  
**Status: ✅ Totalmente Automatizado**
