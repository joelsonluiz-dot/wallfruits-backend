#!/usr/bin/env python3
"""
Monitor de Deploy WallFruits - Render
Monitora o deployment em tempo real
"""
import subprocess
import time
from datetime import datetime

print("=" * 70)
print("🚀 MONITOR DE DEPLOYMENT - RENDER")
print("=" * 70)
print("\n📍 Acompanhando mudanças...\n")

# Histórico anterior
prev_commits = []

while True:
    try:
        # Pega últimos 3 commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd="/workspaces/wallfruits-backend",
            capture_output=True,
            text=True,
            timeout=5
        )
        
        commits = result.stdout.strip().split('\n') if result.stdout else []
        
        if commits != prev_commits:
            print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - Atualizando...\n")
            for i, commit in enumerate(commits):
                prefix = "📌 ÚLTIMO:" if i == 0 else "  "
                print(f"{prefix} {commit}")
            
            # Se último commit era sobre DATABASE_URL
            if "DATABASE_URL" in commits[0] or "Render" in commits[0]:
                print("\n✅ Deploy foi atualizado!")
                print("⏳ Render deve estar redeployando agora...")
                print("📊 Acesse: https://dashboard.render.com para ver logs\n")
            
            prev_commits = commits
        
        # Status do repo
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd="/workspaces/wallfruits-backend",
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if status_result.stdout:
            print(f"📝 Mudanças locais detectadas:")
            print(status_result.stdout)
        
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\n\n👋 Monitor parado.")
        break
    except Exception as e:
        print(f"⚠️ Erro: {e}")
        time.sleep(5)
