#!/usr/bin/env python3
"""
Script para atualizar DATABASE_URL no .env com validação de conexão.

Uso: python scripts/00_update_database_url.py
"""
import sys
import os
import re
from pathlib import Path
from urllib.parse import urlparse

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text

ENV_FILE = Path(__file__).parent.parent / ".env"

print("=" * 70)
print("ATUALIZADOR DE DATABASE_URL - WallFruits")
print("=" * 70)
print("\nCopie a string de conexão PostgreSQL do painel Supabase:")
print("  Supabase Dashboard → Seu Projeto → Connect → PostgreSQL\n")

new_url = input("Database URL: ").strip()

if not new_url or not new_url.startswith("postgresql://"):
    print("\n✗ ERRO: URL inválida (deve começar com 'postgresql://')")
    sys.exit(1)

# Tenta conectar para validar
print("\n🔍 Validando conexão...")
try:
    engine = create_engine(new_url, connect_args={"connect_timeout": 5})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✓ Conexão OK!")
except Exception as e:
    print(f"✗ ERRO ao conectar: {str(e)[:150]}")
    print("\nVerifique:")
    print("  - URL está correta?")
    print("  - Sua senha mudou?")
    print("  - O IP está na whitelist do Supabase?")
    sys.exit(1)

# Atualiza .env
if ENV_FILE.exists():
    content = ENV_FILE.read_text()
    # Replace ou adiciona DATABASE_URL
    pattern = r'DATABASE_URL=.*'
    if re.search(pattern, content):
        content = re.sub(pattern, f'DATABASE_URL={new_url}', content)
    else:
        content = f'DATABASE_URL={new_url}\n' + content
    
    ENV_FILE.write_text(content)
    print(f"\n✓ Atualizado: {ENV_FILE}")
else:
    print(f"\n✗ Arquivo .env não encontrado em {ENV_FILE}")
    sys.exit(1)

print("\n⚠️  Próximos passos:")
print("   1. Atualize DATABASE_URL também no painel do Render")
print("   2. Reinicie a aplicação (local e Render)")
print("   3. Execute: python scripts/01_clear_all_user_data.py")
print("   4. Execute: python scripts/02_create_admin_account.py\n")
