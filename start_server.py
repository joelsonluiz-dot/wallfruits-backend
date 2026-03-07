"""Script para iniciar o servidor WallFruits"""
import uvicorn
import sys
import os

# Garantir que o diretório atual está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 Iniciando WallFruits Backend Server")
    print("=" * 80)
    print("\n📍 Servidor será iniciado em: http://127.0.0.1:8000")
    print("📄 Documentação API: http://127.0.0.1:8000/docs")
    print("🧪 Página de Testes: http://127.0.0.1:8000/qa")
    print("\n" + "=" * 80 + "\n")
    
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
