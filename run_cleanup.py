#!/usr/bin/env python3
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres.adevjuagdmpoyxxuppll:OM5CFKQoDBl2egKF@aws-1-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require&connect_timeout=4'

from sqlalchemy import create_engine, text

print('='*70)
print('LIMPANDO DADOS - WALLFRUITS')
print('='*70)

db_url = os.environ['DATABASE_URL']
engine = create_engine(db_url)

DELETE_ORDER = [
    'review_contestations',
    'reputation_reviews',
    'reviews',
    'offer_images',
    'raffle_tickets',
    'raffles',
    'point_transactions',
    'wallet_transactions',
    'wallets',
    'negotiation_messages',
    'intermediation_contract_versions',
    'intermediation_contracts',
    'intermediation_requests',
    'negotiations',
    'offers',
    'favorites',
    'follows',
    'auth_tokens',
    'badges',
    'subscriptions',
    'messages',
    'notifications',
    'categories',
    'profiles',
    'users',
]

try:
    with engine.begin() as conn:
        total = 0
        for table in DELETE_ORDER:
            try:
                result = conn.execute(text(f'DELETE FROM {table}'))
                rows = result.rowcount if result.rowcount > 0 else 0
                total += rows
                if rows > 0:
                    print(f'✓ {table:40} - {rows:5} deletados')
            except Exception as e:
                pass
    print(f'\n✅ Limpeza concluída! Total: {total} registros deletados')
except Exception as e:
    print(f'ERRO: {e}')
