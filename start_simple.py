"""
Configuração simplificada usando SQLite (sem necessidade de PostgreSQL)
"""
import os

# Forçar uso de SQLite
os.environ["DATABASE_URL"] = "sqlite:///./wallfruits.db"
os.environ["REDIS_ENABLED"] = "false"

# Importar app
from app.main import app

if __name__ == "__main__":
    import uvicorn
    print("=" * 80)
    print("WALLFRUITS - MODO DESENVOLVIMENTO (SQLite)")
    print("=" * 80)
    print("")
    print("✅ Usando banco de dados SQLite (wallfruits.db)")
    print("✅ Redis desabilitado")
    print("")
    print("URLs:")
    print("  📄 API Docs: http://127.0.0.1:8000/docs")
    print("  🧪 Testes:   http://127.0.0.1:8000/qa")
    print("  📁 Teste HTML: Abra o arquivo 'test_api.html' no navegador")
    print("")
    print("=" * 80)
    print("")
    
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
