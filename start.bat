@echo off
echo ===============================================================================
echo           WALLFRUITS BACKEND - SERVIDOR DE DESENVOLVIMENTO
echo ===============================================================================
echo.

cd /d "%~dp0"

echo Verificando ambiente Python...
if not exist ".venv\Scripts\python.exe" (
    echo ERRO: Ambiente virtual nao encontrado!
    echo Execute: python -m venv .venv
    pause
    exit /b 1
)

echo Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo.
echo Iniciando servidor FastAPI...
echo.
echo   URL Principal: http://127.0.0.1:8000
echo   Documentacao:  http://127.0.0.1:8000/docs
echo   Testes QA:     http://127.0.0.1:8000/qa
echo.
echo ===============================================================================
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause
