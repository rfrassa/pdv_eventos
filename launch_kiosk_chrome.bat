@echo off
chcp 65001 >nul
REM Lanzar Google Chrome en modo kiosko con impresion automática (--kiosk-printing)

REM Ajusta la URL del servidor si es necesario
set SERVER_URL=http://192.168.0.200:8080/

REM Rutas habituales de Chrome
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
if not exist "%CHROME_PATH%" (
    set CHROME_PATH=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
)

if not exist "%CHROME_PATH%" (
    echo No se encontro Chrome en las rutas por defecto. Edita este archivo y ajusta CHROME_PATH.
    pause
    exit /b 1
)

REM Opcional: establecer impresora por defecto antes de lanzar (descomenta y ajusta el nombre)
REM powershell -Command "Set-Printer -Name 'EPSONA10498 (L355 Series)' -IsDefault $true"

REM Flags recomendadas:
REM --kiosk: abre en modo kiosko
REM --kiosk-printing: imprime sin dialogo en la impresora por defecto
REM --no-first-run y --disable-infobars reducen mensajes emergentes

start "" "%CHROME_PATH%" --kiosk --kiosk-printing --no-first-run --disable-infobars --disable-session-crashed-bubble --allow-running-insecure-content "%SERVER_URL%"

exit /b 0
