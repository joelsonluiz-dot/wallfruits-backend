@echo off
chcp 65001 > nul
cls
echo ==============================================================================
echo                    WALLFRUITS - SERVIDOR SIMPLES
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Configurando ambiente...
if not exist ".venv" (
    echo ERRO: Ambiente virtual nao encontrado!
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo OK
echo.

echo [2/3] Configurando banco de dados SQLite...
set DATABASE_URL=sqlite:///./wallfruits.db
set REDIS_ENABLED=false
echo OK
echo.

echo [3/3] Iniciando servidor...
echo.
echo   URL: http://127.0.0.1:8000
echo   Docs: http://127.0.0.1:8000/docs
echo   QA: http://127.0.0.1:8000/qa
echo.
echo ==============================================================================
echo IMPORTANTE: Abra o arquivo test_api.html no navegador para testar!
echo ==============================================================================
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level warning

pause
