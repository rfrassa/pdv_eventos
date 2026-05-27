@echo off
chcp 65001 >nul
title PDV Eventos - Servidor
echo ============================================
echo  Iniciando Servidor PDV Eventos
echo ============================================
echo.
echo  IP del servidor:
ipconfig | findstr /i "IPv4"
echo.
echo  Puerto preferido: 8000 (si esta ocupado, usa otro automaticamente)
echo.
echo ============================================
cd /d C:\ibat_pdv_eventos\ibat_pdv_eventos
set PDV_SERVER_BIND=0.0.0.0
set PDV_SERVER_PORT=8000
C:\ibat_pdv_eventos\ibat_pdv_eventos\venv\Scripts\python.exe run_server_local.py --host %PDV_SERVER_BIND% --port %PDV_SERVER_PORT%
pause
