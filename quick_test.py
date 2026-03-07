"""Teste direto de conexão"""
print("Testando conexões...")

# 1. Redis
print("\n1. Redis:")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True, socket_connect_timeout=2)
    r.ping()
    print("   ✅ OK")
except Exception as e:
    print(f"   ❌ ERRO: {e}")

# 2. PostgreSQL
print("\n2. PostgreSQL:")
try:
    from sqlalchemy import create_engine, text
    DATABASE_URL = "postgresql://postgres:Wallfruits%402026@localhost:5432/wallfruits_db"
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("   ✅ OK")
except Exception as e:
    print(f"   ❌ ERRO: {e}")

# 3. Import app
print("\n3. Importando app:")
try:
    from app.main import app
    print(f"   ✅ OK - {app.title}")
except Exception as e:
    print(f"   ❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
