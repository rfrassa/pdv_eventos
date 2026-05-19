@echo off
echo ==========================================
echo  Iniciando Servidor PDV - IBAT 2026
echo ==========================================
echo.
echo Abriendo servidor Django en WSL...
echo Accede desde el movil a: http://192.168.0.52:8000
echo.
echo Para detener: cerrar esta ventana (Ctrl+C)
echo ==========================================
echo.

wsl -d Ubuntu -e /home/rafaelf/ibat_pdv_eventos/venv/bin/python /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/manage.py runserver 0.0.0.0:8000

pause
