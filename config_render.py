#!/usr/bin/env python3
"""
Script para encontrar e exibir as credenciais do Supabase
e gerar configuração para Render
"""

import os
import sys

def get_env_file_content():
    """Tenta ler arquivo .env se existir"""
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            return f.read()
    return None

def check_supabase_vars():
    """Verifica variáveis de ambiente do Supabase"""
    vars_needed = {
        'DATABASE_URL': 'URL do banco de dados PostgreSQL',
        'SUPABASE_URL': 'URL do projeto Supabase',
        'SUPABASE_ANON_KEY': 'Anon Key do Supabase',
        'SUPABASE_SERVICE_ROLE_KEY': 'Service Role Key do Supabase'
    }
    
    print("\n" + "="*70)
    print("🔍 VERIFICANDO VARIÁVEIS DO SUPABASE")
    print("="*70 + "\n")
    
    found_vars = {}
    missing_vars = []
    
    for var, description in vars_needed.items():
        value = os.getenv(var)
        if value:
            found_vars[var] = value
            print(f"✅ {var}: {value[:40]}...")
        else:
            missing_vars.append((var, description))
            print(f"❌ {var}: NÃO ENCONTRADO")
    
    return found_vars, missing_vars

def main():
    print("\n" + "="*70)
    print("🚀 CONFIGURADOR RENDER - WallFruits Backend")
    print("="*70 + "\n")
    
    # Verificar variáveis de ambiente
    found, missing = check_supabase_vars()
    
    print("\n" + "-"*70)
    print("📋 PRÓXIMOS PASSOS:")
    print("-"*70 + "\n")
    
    if missing:
        print("❌ VARIÁVEIS FALTANTES:\n")
        for var, desc in missing:
            print(f"   • {var}")
            print(f"     → {desc}\n")
        
        print("\n💡 COMO ENCONTRAR ESSAS CREDENCIAIS:\n")
        print("1. Acesse: https://supabase.com/dashboard")
        print("2. Clique em seu projeto (wallfruits ou similar)")
        print("3. Vá em 'Settings' → 'Database'")
        print("   → PROJECT_URL = SUPABASE_URL")
        print("   → Connection string = DATABASE_URL\n")
        print("4. Vá em 'Settings' → 'API'")
        print("   → anon public = SUPABASE_ANON_KEY")
        print("   → service_role secret = SUPABASE_SERVICE_ROLE_KEY\n")
        
    print("\n" + "="*70)
    print("📌 COMO CONFIGURAR NO RENDER:")
    print("="*70 + "\n")
    print("1. Acesse: https://dashboard.render.com")
    print("2. Selecione serviço: wallfruits-api")
    print("3. Acesse aba: 'Environment'")
    print("4. Clique: 'Add Environment Variable' para cada uma:\n")
    
    all_vars = {
        'DATABASE_URL': 'Sua URL do PostgreSQL (com postgresql://)',
        'SUPABASE_URL': 'https://seu-projeto.supabase.co',
        'SUPABASE_ANON_KEY': 'Sua chave anon do Supabase',
        'SUPABASE_SERVICE_ROLE_KEY': 'Sua service role key do Supabase',
        'SUPABASE_AUTH_ENABLED': 'true (ou false se não usar auth)',
        'DEBUG': 'false',
        'REDIS_ENABLED': 'false (plano gratis)'
    }
    
    for i, (var, example) in enumerate(all_vars.items(), 1):
        value = found.get(var, f"← {example}")
        print(f"   {i}. Key: {var}")
        print(f"      Value: {value}\n")
    
    print("\n5. Clique em 'Save Changes'")
    print("6. Clique em 'Manual Deploy' → 'Deploy Latest Commit'")
    print("7. Aguarde ~5 minutos o build terminar\n")
    
    print("="*70)
    print("✅ Quando ver 'Live' em verde:")
    print("="*70 + "\n")
    print("  Teste seus endpoints:")
    print("  • https://wallfruits-api.onrender.com/health")
    print("  • https://wallfruits-api.onrender.com/docs\n")

if __name__ == "__main__":
    main()
