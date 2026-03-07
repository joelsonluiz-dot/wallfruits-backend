"""
Script completo para resetar e configurar o banco de dados
"""
import sys

print("=" * 80)
print("WALLFRUITS - CONFIGURAÇÃO DO BANCO DE DADOS")
print("=" * 80)

# Passo 1: Testar conexão PostgreSQL
print("\n[1/4] Testando conexão PostgreSQL...")
try:
    import psycopg2
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="postgres",  # Conectar ao banco padrão primeiro
        user="postgres",
        password="Wallfruits@2026",
        connect_timeout=5
    )
    conn.autocommit = True
    cur = conn.cursor()
    print("      ✅ PostgreSQL conectado")
    
    # Verificar se o banco wallfruits_db existe
    cur.execute("SELECT 1 FROM pg_database WHERE datname='wallfruits_db'")
    exists = cur.fetchone()
    
    if not exists:
        print("      📦 Criando banco de dados wallfruits_db...")
        cur.execute("CREATE DATABASE wallfruits_db")
        print("      ✅ Banco criado")
    else:
        print("      ✅ Banco wallfruits_db já existe")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"      ❌ ERRO: {e}")
    print("\n💡 Verifique se:")
    print("   - PostgreSQL está instalado")
    print("   - PostgreSQL está rodando")
    print("   - Usuário: postgres / Senha: Wallfruits@2026")
    sys.exit(1)

# Passo 2: Deletar e recriar tabelas
print("\n[2/4] Resetando tabelas...")
try:
    from sqlalchemy import create_engine, inspect, text
    from app.database.connection import Base
    from app.models import User, Offer, Transaction, Review, Favorite, Message, Category
    
    DATABASE_URL = "postgresql://postgres:Wallfruits%402026@localhost:5432/wallfruits_db"
    engine = create_engine(DATABASE_URL)
    
    # Dropar todas as tabelas
    print("      🔨 Removendo tabelas antigas...")
    Base.metadata.drop_all(bind=engine)
    print("      ✅ Tabelas removidas")
    
    # Criar tabelas novamente
    print("      🔨 Criando tabelas novas...")
    Base.metadata.create_all(bind=engine)
    print("      ✅ Tabelas criadas")
    
    # Verificar tabelas criadas
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"      📊 Tabelas: {', '.join(tables)}")
    
except Exception as e:
    print(f"      ❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Passo 3: Criar usuário admin
print("\n[3/4] Criando usuário administrador...")
try:
    from sqlalchemy.orm import Session
    from app.models.user import User
    from app.auth.password_hash import hash_password
    
    with Session(engine) as session:
        # Verificar se já existe admin
        admin = session.query(User).filter_by(email="admin@wallfruits.com").first()
        
        if not admin:
            admin_user = User(
                name="Administrador",
                email="admin@wallfruits.com",
                password=hash_password("admin123"),
                role="admin",
                is_active=True,
                is_verified=True
            )
            session.add(admin_user)
            session.commit()
            print(f"      ✅ Admin criado (ID: {admin_user.id})")
            print("      📧 Email: admin@wallfruits.com")
            print("      🔑 Senha: admin123")
        else:
            print(f"      ✅ Admin já existe (ID: {admin.id})")
            
except Exception as e:
    print(f"      ⚠️ Aviso: {e}")

# Passo 4: Teste final
print("\n[4/4] Teste de conectividade...")
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        print(f"      ✅ Banco funcional - {count} usuário(s) cadastrado(s)")
except Exception as e:
    print(f"      ❌ ERRO: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!")
print("=" * 80)
print("\nPróximos passos:")
print("  1. Inicie o Redis: cd redis && .\\redis-server.exe redis.windows.conf")
print("  2. Inicie o servidor: python -m uvicorn app.main:app --reload")
print("  3. Abra o arquivo: test_api.html no navegador")
print("=" * 80)
