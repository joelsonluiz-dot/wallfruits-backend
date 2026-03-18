#!/usr/bin/env python3
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres.adevjuagdmpoyxxuppll:OM5CFKQoDBl2egKF@aws-1-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require&connect_timeout=4'

from datetime import datetime
from sqlalchemy import create_engine, text
from app.auth.password_hash import hash_password

print('='*70)
print('CRIANDO CONTA ADMIN - WALLFRUITS')
print('='*70)

ADMIN_EMAIL = "admin@wallfruits.com.br"
ADMIN_PASSWORD = "Admin@2026Wallfruits"
ADMIN_PHONE = "+55 (62) 98888-0001"

password_hash = hash_password(ADMIN_PASSWORD)
db_url = os.environ['DATABASE_URL']
engine = create_engine(db_url)

try:
    with engine.begin() as conn:
        # Verifica se existir
        result = conn.execute(text("SELECT id FROM users WHERE email = :email LIMIT 1"), 
                            {"email": ADMIN_EMAIL})
        if result.scalar():
            conn.execute(text("DELETE FROM users WHERE email = :email"), 
                        {"email": ADMIN_EMAIL})
            print("ℹ️  Admin anterior deletado")
        
        # Cria novo
        now = datetime.utcnow().isoformat()
        conn.execute(text("""
            INSERT INTO users (
                email, phone, password_hash, role, is_superuser, 
                is_active, email_verified, created_at, updated_at
            )
            VALUES (
                :email, :phone, :password_hash, 'admin', true,
                true, true, :now, :now
            )
        """), {
            "email": ADMIN_EMAIL,
            "phone": ADMIN_PHONE,
            "password_hash": password_hash,
            "now": now
        })
        
    print("\n" + "="*70)
    print("✅ ADMIN CRIADO COM SUCESSO!")
    print("="*70)
    print(f"\n📧 Email:   {ADMIN_EMAIL}")
    print(f"🔐 Senha:   {ADMIN_PASSWORD}")
    print(f"📱 Tel:     {ADMIN_PHONE}")
    print(f"⭐ Role:    admin (superuser)")
    print("\n" + "="*70)
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
