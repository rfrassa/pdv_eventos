@echo off
chcp 65001 >nul
REM Lanzar Google Chrome en modo kiosko con impresion automatica

set SERVER_URL=http://192.168.0.200:8080/
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
if not exist "%CHROME_PATH%" (
    set CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
)

if not exist "%CHROME_PATH%" (
    echo No se encontro Chrome. Edita CHROME_PATH en este archivo.
    pause
    exit /b 1
)

REM Cerrar cualquier instancia previa (necesario para que --kiosk tome efecto)
taskkill /F /IM chrome.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul

start "" "%CHROME_PATH%" --kiosk --kiosk-printing --no-first-run --disable-infobars --disable-session-crashed-bubble --allow-running-insecure-content --force-device-scale-factor=1 --user-data-dir="C:\ChromeKiosk" "%SERVER_URL%"

exit /b 0
