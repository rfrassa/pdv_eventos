@echo off
chcp 65001 >nul
title PDV - Inicio

echo Iniciando servidor Django...
start "PDV Servidor" cmd /k "%~dp0ibat_pdv_eventos\iniciar_servidor_eth_fijo.bat"

echo Esperando que el servidor responda en el puerto 8080...
set /a INTENTOS=0
:esperar
powershell -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1',8080); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto listo
set /a INTENTOS+=1
if %INTENTOS% geq 60 (
  echo [ERROR] El servidor no respondio en 2 minutos. Revisar la ventana "PDV Servidor".
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto esperar
:listo

echo Iniciando Chrome kiosk...
call "%~dp0launch_kiosk_chrome.bat"
