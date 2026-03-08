# 🚀 COMANDOS FINAIS - Cole no Terminal do VS Code

## 1️⃣ Abrir terminal limpo
Pressione `Ctrl + Shift + '` (abre terminal novo)

## 2️⃣ Colar estes comandos (um de cada vez):

```powershell
# Limpar Git anterior
Remove-Item -Recurse -Force .git -ErrorAction SilentlyContinue

# Inicializar Git
git init

# Configurar usuário
git config user.email "joelson.luiz@aluno.ifsertao-pe.edu.br"
git config user.name "joelsonluiz-dot"

# Adicionar todos os arquivos
git add .

# Fazer commit
git commit -m "Deploy Render - WallFruits API"

# Criar branch main
git branch -M main

# Adicionar repositório remoto
git remote add origin https://github.com/joelsonluiz-dot/wallfruits-backend.git

# UPLOAD PARA GITHUB (vai pedir senha)
git push -u origin main
```

---

## ⚠️ Quando pedir senha:

**Username:** `joelsonluiz-dot`

**Password:** NÃO use sua senha normal do GitHub!

Use um **Personal Access Token**:

1. Abra: https://github.com/settings/tokens
2. Clique "Generate new token" → "Classic"
3. Nota: `Deploy Render`
4. Marque: `repo` (todos os checkboxes)
5. Gere e **copie o token**
6. Cole no terminal (não aparece, mas está digitando)
7. Enter

---

## 3️⃣ Depois que o push funcionar:

### **Ir no Render:** https://render.com/

1. Login com GitHub (já está logado)
2. Dashboard → "New +" → "Blueprint"
3. Conectar repositório `wallfruits-backend`
4. Render detecta o `render.yaml` automaticamente
5. Clique "Apply"

**PRONTO! Render cria tudo sozinho!** 🎉

---

## ✅ Em 5 minutos sua API estará no ar:

```
https://wallfruits-api.onrender.com/health
https://wallfruits-api.onrender.com/docs
https://wallfruits-api.onrender.com/qa
```

---

## 💡 Se o token não funcionar:

Use GitHub Desktop (mais fácil):

1. Baixe: https://desktop.github.com/
2. Instale e faça login
3. File → Add Local Repository
4. Escolha `C:\Users\User\Desktop\wallfruits-backend`
5. Publish repository
6. Pronto!

Depois siga para o Render (passo 3).
