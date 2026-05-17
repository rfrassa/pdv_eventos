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
echo  Acceder desde: http://^<IP_mostrada^>:8000
echo.
echo ============================================
cd /d C:\ibat_pdv_eventos\ibat_pdv_eventos
C:\ibat_pdv_eventos\ibat_pdv_eventos\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
pause
