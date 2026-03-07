# 🍎 WallFruits Backend - Guia de Inicialização

## ⚠️ PROBLEMA IDENTIFICADO

O servidor não consegue iniciar porque:
1. ❌ **PostgreSQL não está rodando** (ou não instalado)
2. ❌ **Redis pode não estar acessível**

## ✅ SOLUÇÃO RÁPIDA (Modo Simplificado)

### Opção 1: Executar Script BAT (RECOMENDADO)

Abra um terminal PowerShell e execute:

```bat
.\start-simples.bat
```

Este script:
- ✅ Usa SQLite (não precisa de PostgreSQL)
- ✅ Funciona sem Redis
- ✅ Cria banco de dados automaticamente

### Opção 2: Comando Manual

```powershell
# 1. Ativar ambiente virtual
.\.venv\Scripts\Activate.ps1

# 2. Configurar banco SQLite
$env:DATABASE_URL = "sqlite:///./wallfruits.db"

# 3. Iniciar servidor
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 🧪 TESTANDO A API

Após iniciar o servidor, você tem 3 opções:

### 1️⃣ Arquivo HTML de Teste (MAIS FÁCIL)
Abra no navegador:
```
C:\Users\User\Desktop\wallfruits-backend\test_api.html
```

### 2️⃣ Página QA do Servidor
```
http://127.0.0.1:8000/qa
```

### 3️⃣ Documentação Automática
```
http://127.0.0.1:8000/docs
```

## 🔧 PROBLEMAS COMUNS

### "ModuleNotFoundError: No module named 'imghdr'"
✅ JÁ CORRIGIDO - Removi dependência do imghdr (removido no Python 3.13)

### "Connection timeout" no PostgreSQL
✅ Use o script `start-simples.bat` que usa SQLite

"Redis connection failed"
✅ O código agora funciona sem Redis

### Porta 8000 já em uso
Altere a porta no comando:
```
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## 📁 ARQUIVOS CRIADOS PARA VOCÊ

| Arquivo | Descrição |
|---------|-----------|
| `test_api.html` | Interface de teste que abre no navegador |
| `start-simples.bat` | Script para iniciar servidor com SQLite |
| `start_simple.py` | Versão Python do script simplificado |
| `setup_database.py` | Configurador de banco (PostgreSQL) |
| `check_services.py` | Diagnóstico de serviços |

## 🚀 COMEÇAR AGORA

Execute este comando:
```powershell
.\start-simples.bat
```

Depois abra no navegador:
```
test_api.html
```

Pronto! Você terá uma interface visual para testar todas as funcionalidades da API.

## 📞 SUPORTE

Se mesmo assim não funcionar, execute:
```powershell
python check_services.py
```

E envie o resulta output para diagnóstico.
