@echo off
setlocal
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "PID_FILE=%ROOT%logs\run_web.pid"
set "URL=http://127.0.0.1:8765"

if not exist "%VENV_PY%" (
    echo Python virtualenv nao encontrado em %VENV_PY%
    echo Execute primeiro: python -m venv .venv
    pause
    exit /b 1
)

if not exist "%ROOT%logs" mkdir "%ROOT%logs"

:menu
cls
echo.
echo ==========================
echo AUTO TEST - QUICK START
echo ==========================
echo START   - inicia o app web local
echo STOP    - para o servidor
echo LOCAL   - abre o link local
echo.
set /p choice="Escolha [START/STOP/LOCAL]: "
if /I "%choice%"=="START" goto :start
if /I "%choice%"=="STOP" goto :stop
if /I "%choice%"=="LOCAL" goto :local

echo Opcao invalida.
pause >nul
goto :menu

:start
if exist "%PID_FILE%" (
    set "PID="
    for /f "usebackq delims=" %%i in ("%PID_FILE%") do set "PID=%%i"
    if defined PID (
        taskkill /F /PID "%PID%" >nul 2>&1
    )
)
powershell -NoProfile -Command "$p = Start-Process -FilePath '%VENV_PY%' -ArgumentList 'run_web.py' -WorkingDirectory '%ROOT%' -PassThru; $p.Id | Set-Content '%PID_FILE%'"
echo.
echo Servidor iniciado.
echo Link local: %URL%
echo.
echo Pressione qualquer tecla para voltar ao menu...
pause >nul
goto :menu

:stop
if exist "%PID_FILE%" (
    set "PID="
    for /f "usebackq delims=" %%i in ("%PID_FILE%") do set "PID=%%i"
    if defined PID (
        taskkill /F /PID "%PID%" >nul 2>&1
        del "%PID_FILE%" >nul 2>&1
        echo Servidor parado.
    ) else (
        echo Nenhum processo ativo encontrado.
    )
) else (
    echo Nenhum processo ativo encontrado.
)
echo.
pause >nul
goto :menu

:local
start "" "%URL%"
echo Abrindo o link local...
echo %URL%
echo.
pause >nul
goto :menu
