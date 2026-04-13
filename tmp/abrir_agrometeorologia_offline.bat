@echo off
setlocal

set "SCRIPT_PATH=%~dp0agrometeorologia_prova_offline.py"

if not exist "%SCRIPT_PATH%" (
    echo Erro: script nao encontrado em:
    echo %SCRIPT_PATH%
    pause
    exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%SCRIPT_PATH%"
    goto :end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%SCRIPT_PATH%"
    goto :end
)

echo Python nao encontrado no sistema.
echo Instale Python ou habilite o comando py.
pause
exit /b 1

:end
endlocal
