@echo off
chcp 65001 >nul
title PDV - Inicio

echo Iniciando servidor Django...
start "PDV Servidor" cmd /k "%~dp0ibat_pdv_eventos\iniciar_servidor_eth_fijo.bat"

echo Esperando que el servidor levante (8 segundos)...
timeout /t 8 /nobreak >nul

echo Iniciando Chrome kiosk...
call "%~dp0launch_kiosk_chrome.bat"
