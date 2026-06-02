# Instalador sencillo: crea una tarea programada que arranca el agente al iniciar sesión
# Uso: ejecutar con permisos de administrador
$agentDir = Join-Path $PSScriptRoot '..\print_agent'
$agentMain = Join-Path $agentDir 'main.py'
$taskName = 'PDV Print Agent'

if (-not (Test-Path $agentMain)) {
    Write-Error "No se encontró $agentMain. Ajustá la ruta al agente."
    exit 1
}

# Localizar Python
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    Write-Host "No se encontró python en PATH. Ingresá la ruta completa a python.exe:" -NoNewline
    $python = Read-Host
}

$action = "`"$python`" `"$agentMain`""
Write-Host "Creando tarea programada '$taskName' que ejecuta: $action"

# Crear tarea que se ejecute al iniciar sesión del usuario actual
schtasks /Create /TN "$taskName" /TR $action /SC ONLOGON /RL HIGHEST /F | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Tarea creada correctamente."
} else {
    Write-Error "Error creando la tarea programada. Código: $LASTEXITCODE"
}

Write-Host "Para iniciar el agente ahora:"
Write-Host "Start-Process -FilePath $python -ArgumentList \"$agentMain\" -WindowStyle Hidden"