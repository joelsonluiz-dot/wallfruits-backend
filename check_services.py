"""Verificar status completo dos serviços"""
import sys

print("=" * 80)
print("DIAGNÓSTICO DE SERVIÇOS - WallFruits Backend")
print("=" * 80)

# 1. Redis
print("\n1️⃣ Testando Redis (localhost:6379)...")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=2)
    r.ping()
    print("   ✅ Redis ATIVO e respondendo")
except redis.ConnectionError as e:
    print(f"   ❌ Redis OFFLINE: {e}")
    print("   💡 Inicie com: redis\\redis-server.exe redis\\redis.windows.conf")
except Exception as e:
    print(f"   ❌ Erro ao testar Redis: {e}")

# 2. PostgreSQL
print("\n2️⃣ Testando PostgreSQL (localhost:5432)...")
try:
    import psycopg2
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="wallfruits_db",
        user="postgres",
        password="Wallfruits@2026",
        connect_timeout=3
    )
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()
    cur.close()
    conn.close()
    print(f"   ✅ PostgreSQL ATIVO")
    print(f"   📊 Versão: {version[0][:50]}...")
except psycopg2.OperationalError as e:
    print(f"   ❌ PostgreSQL OFFLINE ou inacessível")
    print(f"   💡 Erro: {str(e)[:100]}")
    print("   💡 Verifique se o PostgreSQL está instalado e rodando")
    print("   💡 Verifique usuário/senha: postgres/Wallfruits@2026")
except ImportError:
    print("   ⚠️ Módulo psycopg2 não instalado (usando SQLAlchemy)")
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine("postgresql://postgres:Wallfruits%402026@localhost:5432/wallfruits_db")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()
            print(f"   ✅ PostgreSQL ATIVO (via SQLAlchemy)")
            print(f"   📊 Versão: {version[0][:50]}...")
    except Exception as e2:
        print(f"   ❌ PostgreSQL OFFLINE: {e2}")
except Exception as e:
    print(f"   ❌ Erro ao testar PostgreSQL: {e}")

# 3. Porta 8000  
print("\n3️⃣ Verificando porta 8000...")
try:
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8000))
    if result == 0:
        print("   ⚠️ Porta 8000 JÁ ESTÁ EM USO")
        print("   💡 Pode haver um servidor rodando ou use outra porta")
    else:
        print("   ✅ Porta 8000 livre e disponível")
    sock.close()
except Exception as e:
    print(f"   ❓ Não foi possível verificar porta: {e}")

print("\n" + "=" * 80)
print("RESUMO")
print("=" * 80)
print("\nPara o servidor funcionar, você precisa:")
print("  ✓ Redis rodando (localhost:6379)")
print("  ✓ PostgreSQL rodando (localhost:5432)")
print("  ✓ Porta 8000 livre")
print("\nSe todos estiverem OK, execute:")
print("  python start_server.py")
print("=" * 80)
