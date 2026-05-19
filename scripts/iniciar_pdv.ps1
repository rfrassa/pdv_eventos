Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Iniciando Servidor PDV - IBAT 2026" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Obtener IP de WSL
$wslIp = wsl -d Ubuntu -e ip addr show eth0 | Select-String "inet " | ForEach-Object { $_ -replace '.*inet (\d+\.\d+\.\d+\.\d+).*', '$1' }
Write-Host "WSL IP: $wslIp" -ForegroundColor Yellow

# Configurar port forwarding (necesita admin)
try {
    netsh interface portproxy delete v4tov4 listenport=8000 2>$null
    netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=$wslIp connectport=8000
    netsh advfirewall firewall delete rule name="Django 8000" 2>$null
    netsh advfirewall firewall add rule name="Django 8000" dir=in action=allow protocol=TCP localport=8000
    Write-Host "Port forwarding configurado" -ForegroundColor Green
} catch {
    Write-Host "Port forwarding requiere administrador. Ejecuta como Admin o usa scripts/setup_mobile_access.sh" -ForegroundColor Yellow
}

# Obtener IP de Windows LAN
$winIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' }).IPAddress
Write-Host ""
Write-Host "Accede desde el movil a: http://$winIp`:8000" -ForegroundColor Green
Write-Host ""

# Iniciar Django en WSL
Write-Host "Iniciando Django..." -ForegroundColor Yellow
wsl -d Ubuntu -e /home/rafaelf/ibat_pdv_eventos/venv/bin/python /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/manage.py runserver 0.0.0.0:8000

Read-Host "`nPresiona Enter para salir"
