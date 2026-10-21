@echo off
chcp 65001 >nul
REM Lanzar Google Chrome en modo kiosko con impresion automatica

set SERVER_URL=http://192.168.0.200:8080/
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
REM OJO: no poner "(x86)" dentro de un bloque if ( ... ): el ")" cierra el bloque y rompe el .bat
if exist "%CHROME_PATH%" goto :chrome_ok
set "CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
:chrome_ok

if not exist "%CHROME_PATH%" (
    echo No se encontro Chrome. Edita CHROME_PATH en este archivo.
    pause
    exit /b 1
)

REM Cerrar solo el Chrome del kiosco (perfil ChromeKiosk); no toca otros Chrome abiertos
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object CommandLine -match 'ChromeKiosk' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

start "" "%CHROME_PATH%" --kiosk --kiosk-printing --no-first-run --disable-infobars --disable-session-crashed-bubble --allow-running-insecure-content --force-device-scale-factor=1 --user-data-dir="C:\ChromeKiosk" "%SERVER_URL%"

exit /b 0
