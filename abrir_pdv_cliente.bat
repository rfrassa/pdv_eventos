@echo off
setlocal
chcp 65001 >nul

REM IP fija de la PC servidor en la red Ethernet
set SERVER_IP=192.168.0.53
set SERVER_PORT=8080

start "" "http://%SERVER_IP%:%SERVER_PORT%/"

endlocal
