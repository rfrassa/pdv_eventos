#!/bin/bash
# Configura port forwarding desde Windows hacia WSL para Django
# Ejecutar: bash scripts/setup_mobile_access.sh

WSL_IP=$(ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
echo "WSL IP: $WSL_IP"

echo ""
echo "=== Opcion 1: Ejecutar auto (pide admin) ==="
powershell.exe -Command "
Start-Process PowerShell -Verb RunAs -ArgumentList '-NoProfile -Command \"
    netsh interface portproxy delete v4tov4 listenport=8000 2> nul;
    netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=$WSL_IP connectport=8000;
    netsh advfirewall firewall delete rule name='Django 8000' 2> nul;
    netsh advfirewall firewall add rule name='Django 8000' dir=in action=allow protocol=TCP localport=8000;
    Write-Host '';
    Write-Host 'PORT FORWARDING CONFIGURADO' -ForegroundColor Green;
    \$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { \$_.IPAddress -like '192.168.*' }).IPAddress;
    Write-Host 'Accede desde el movil a: http://'\$ip':8000' -ForegroundColor Cyan;
\" -WindowStyle Normal -Wait
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "Configurado correctamente"
    echo ""
    # Show Windows LAN IP
    WIN_IP=$(powershell.exe -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { \$_.IPAddress -like '192.168.*' }).IPAddress" 2>/dev/null)
    echo "Accede desde el movil a: http://$WIN_IP:8000"
else
    echo ""
    echo "=== Opcion 2: Manual (copiar y pegar) ==="
    echo ""
    echo "1) Abri PowerShell como ADMINISTRADOR en Windows"
    echo "2) Ejecuta:"
    echo ""
    echo "netsh interface portproxy delete v4tov4 listenport=8000"
    echo "netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=$WSL_IP connectport=8000"
    echo "netsh advfirewall firewall delete rule name='Django 8000'"
    echo "netsh advfirewall firewall add rule name='Django 8000' dir=in action=allow protocol=TCP localport=8000"
    echo ""
    echo "3) Accede desde el movil a: http://IP_WINDOWS:8000"
    echo "   (la IP de Windows en la LAN, ej: 192.168.0.52)"
fi
