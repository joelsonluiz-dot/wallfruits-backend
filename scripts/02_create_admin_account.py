#!/usr/bin/env python3
"""
Script de criação de conta admin.

Uso: python scripts/02_create_admin_account.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from app.auth.password_hash import hash_password

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não configurada no .env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

# Credenciais do admin
ADMIN_EMAIL = "admin@wallfruits.com.br"
ADMIN_PASSWORD = "Admin@2026Wallfruits"  # Mude depois de primeiro login!
ADMIN_PHONE = "+55 (62) 98888-0001"

# Hash da senha
password_hash = hash_password(ADMIN_PASSWORD)

print("=" * 70)
print("CRIADOR DE CONTA ADMIN - WallFruits")
print("=" * 70)
print(f"\n📧 Email: {ADMIN_EMAIL}")
print(f"🔐 Senha: {ADMIN_PASSWORD}")
print(f"📱 Telefone: {ADMIN_PHONE}\n")

try:
    with engine.begin() as conn:
        # Verifica se admin já existe
        result = conn.execute(text("""
            SELECT id FROM users WHERE email = :email LIMIT 1
        """), {"email": ADMIN_EMAIL})
        
        if result.scalar():
            print("⚠️  Admin já existe no banco. Deletando versão anterior...")
            conn.execute(text("DELETE FROM users WHERE email = :email"), {"email": ADMIN_EMAIL})
        
        # Cria novo admin
        now = datetime.utcnow().isoformat()
        conn.execute(text("""
            INSERT INTO users (
                email, 
                phone, 
                password_hash, 
                role, 
                is_superuser, 
                is_active, 
                email_verified,
                created_at, 
                updated_at
            )
            VALUES (
                :email,
                :phone,
                :password_hash,
                'admin',
                true,
                true,
                true,
                :now,
                :now
            )
        """), {
            "email": ADMIN_EMAIL,
            "phone": ADMIN_PHONE,
            "password_hash": password_hash,
            "now": now
        })
        
        print("✓ Admin criado com sucesso!\n")
        print("=" * 70)
        print("CREDENCIAIS DE ACESSO:")
        print("=" * 70)
        print(f"Email:    {ADMIN_EMAIL}")
        print(f"Senha:    {ADMIN_PASSWORD}")
        print(f"Role:     admin (superuser)")
        print("=" * 70)
        print("\n⚠️  IMPORTANTE:")
        print("   1. Mude a senha após primeiro login")
        print("   2. Guarde essas credenciais em local seguro")
        print("   3. Não compartilhe a senha com ninguém\n")
        
except Exception as e:
    print(f"✗ ERRO ao criar admin: {e}")
    sys.exit(1)
