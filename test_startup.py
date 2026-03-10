"""Script para testar inicialização da aplicação"""
import sys
import traceback
import sqlalchemy

failures = []

print("=" * 80)
print("TESTE DE INICIALIZAÇÃO - WallFruits Backend")
print("=" * 80)

# 1. Testar imports básicos
print("\n1️⃣ Testando imports básicos...")
try:
    from fastapi import FastAPI
    from sqlalchemy import create_engine
    import redis
    print("   ✅ Imports básicos OK")
except Exception as e:
    print(f"   ❌ Erro nos imports: {e}")
    traceback.print_exc()
    failures.append("imports basicos")

# 2. Testar configuração
print("\n2️⃣ Testando configurações...")
strict_startup = True
try:
    from app.core.config import settings
    print(f"   ✅ DATABASE_URL: {settings.DATABASE_URL[:30]}...")
    print(f"   ✅ API_VERSION: {settings.API_VERSION}")
    strict_startup = settings.STRICT_STARTUP
except Exception as e:
    print(f"   ❌ Erro nas configurações: {e}")
    traceback.print_exc()
    failures.append("configuracoes")

# 3. Testar Redis
print("\n3️⃣ Testando conexão Redis...")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.ping()
    print("   ✅ Redis conectado com sucesso")
except Exception as e:
    print(f"   ⚠️ Redis não disponível: {e}")
    print("   (Isso pode impedir o servidor de iniciar)")

# 4. Testar Database
print("\n4️⃣ Testando conexão PostgreSQL...")
try:
    from app.database.connection import engine
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text("SELECT 1"))
        print("   ✅ PostgreSQL conectado com sucesso")
except Exception as e:
    print(f"   ❌ PostgreSQL não disponível: {e}")
    if strict_startup:
        print("   (Servidor NÃO vai iniciar sem o banco porque STRICT_STARTUP=true)")
        traceback.print_exc()
    else:
        print("   (Modo degradado permitido: STRICT_STARTUP=false)")
    if strict_startup:
        failures.append("database")

# 5. Testar imports de modelos
print("\n5️⃣ Testando imports de modelos...")
try:
    from app.models import User, Offer, Transaction
    print("   ✅ Modelos carregados")
except Exception as e:
    print(f"   ❌ Erro nos modelos: {e}")
    traceback.print_exc()
    failures.append("modelos")

# 6. Testar app principal
print("\n6️⃣ Testando app.main...")
try:
    from app.main import app
    print("   ✅ Aplicação FastAPI criada com sucesso")
    print(f"   ✅ Título: {app.title}")
except Exception as e:
    print(f"   ❌ Erro ao criar app: {e}")
    traceback.print_exc()
    failures.append("app.main")

if failures:
    print("\n" + "=" * 80)
    print(f"❌ FALHAS DETECTADAS: {', '.join(failures)}")
    print("=" * 80)
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ TODOS OS TESTES PASSARAM - Servidor pode ser iniciado!")
print("=" * 80)
print("\nPara iniciar o servidor execute:")
print("python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload")
