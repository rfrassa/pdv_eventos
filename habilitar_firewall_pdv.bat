@echo off
setlocal
chcp 65001 >nul

echo ===========================================
echo  Habilitar Firewall - PDV Eventos
echo ===========================================

echo Este script requiere permisos de Administrador.
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo [ERROR] Abri este .bat como "Ejecutar como administrador".
  pause
  exit /b 1
)

for %%P in (8000 8080 8010 8888 9000) do (
  netsh advfirewall firewall add rule name="PDV Eventos %%P" dir=in action=allow protocol=TCP localport=%%P profile=any >nul 2>&1
)

echo [OK] Reglas de firewall creadas/actualizadas.
echo Puertos habilitados: 8000, 8080, 8010, 8888, 9000
echo.
echo Verificacion:
netsh advfirewall firewall show rule name=all | findstr /i "PDV Eventos"

endlocal
pause
