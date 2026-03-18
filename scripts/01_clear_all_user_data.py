#!/usr/bin/env python3
"""
Script de limpeza segue: apaga todos usuários e dados relacionados.
Respeita foreign keys e cascata de deletions.

Uso: python scripts/01_clear_all_user_data.py
"""
import sys
import os
from pathlib import Path

# Adiciona raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não configurada no .env")
    sys.exit(1)

print(f"Conectando ao banco: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")
engine = create_engine(DATABASE_URL)

# Ordem de deleção respeitando FKs
DELETE_ORDER = [
    "review_contestations",  # Depende de reviews
    "reputation_reviews",     # Depende de reviews
    "reviews",                # Depende de negotiations
    "offer_images",           # Depende de offers
    "raffle_tickets",         # Depende de raffles
    "raffles",                # Depende de profiles
    "point_transactions",     # Depende de profiles
    "wallet_transactions",    # Depende de wallets
    "wallets",                # Depende de profiles
    "negotiation_messages",   # Depende de negotiations
    "intermediation_contract_versions",  # Depende de contracts
    "intermediation_contracts",  # Depende de requests
    "intermediation_requests",   # Depende de negotiations
    "negotiations",           # Depende de profiles/offers
    "offers",                 # Depende de profiles
    "favorites",              # Depende de profiles/offers
    "follows",                # Depende de profiles
    "auth_tokens",            # Depende de users
    "badges",                 # Sistema, sem FK direto
    "subscriptions",          # Depende de users
    "messages",               # Depende de profiles
    "notifications",          # Depende de users
    "categories",             # Sistema, sem FK direto
    "profiles",               # Depende de users
    "users",                  # Principal
]

try:
    with engine.begin() as conn:
        # Desabilita constraints temporariamente (PostgreSQL)
        try:
            conn.execute(text("SET session_replication_role = replica"))
        except:
            pass  # SQLite não suporta, ignora
        
        for table in DELETE_ORDER:
            try:
                # Verifica se tabela existe
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )
                """))
                
                if not result.scalar():
                    print(f"  ⊘ Tabela '{table}' não existe, pulando...")
                    continue
                
                # Delete
                result = conn.execute(text(f"DELETE FROM {table}"))
                deleted = result.rowcount
                print(f"  ✓ {table:40} - {deleted:5} registros deletados")
                
            except Exception as e:
                print(f"  ✗ {table:40} - ERRO: {str(e)[:80]}")
        
        # Reabilita constraints
        try:
            conn.execute(text("SET session_replication_role = default"))
        except:
            pass
        
        print("\n✓ Limpeza concluída com sucesso!")
        
except Exception as e:
    print(f"\n✗ ERRO CRÍTICO: {e}")
    sys.exit(1)
