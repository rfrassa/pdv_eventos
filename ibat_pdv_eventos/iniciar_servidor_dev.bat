@echo off
setlocal
chcp 65001 >nul
title PDV Eventos - Servidor (DEBUG)

REM Start local server with DEBUG=1 to serve admin static during setup
set PDV_SERVER_IP=
for /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /i "IPv4"') do (
    set PDV_SERVER_IP=%%I
    goto :ip_found
)

:ip_found
if defined PDV_SERVER_IP (
    for /f "tokens=* delims= " %%A in ("%PDV_SERVER_IP%") do set PDV_SERVER_IP=%%A
)

if not defined PDV_SERVER_IP set PDV_SERVER_IP=127.0.0.1
if "%PDV_SERVER_IP%"=="+" set PDV_SERVER_IP=127.0.0.1

set DJANGO_DEBUG=1
set DJANGO_ALLOWED_HOSTS=*
set PDV_SERVER_BIND=0.0.0.0
set PDV_SERVER_PORT=8080

cd /d %~dp0

echo ============================================
echo  Servidor local (DEBUG=true) detectado en: %PDV_SERVER_IP%:%PDV_SERVER_PORT%
echo ============================================
venv\Scripts\python.exe run_server_local.py --host %PDV_SERVER_BIND% --port %PDV_SERVER_PORT%

endlocal
pause
