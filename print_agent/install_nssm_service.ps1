<#
Instala NSSM (si es necesario) y crea un servicio Windows para el Print Agent.
Ejecútalo como Administrador desde la carpeta del agente.

Uso: Ejecutar PowerShell como Administrador y desde el directorio donde esté este script:
.
    .\install_nssm_service.ps1

El script intentará descargar NSSM si no está presente.
#>

Set-StrictMode -Version Latest

function Ensure-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
    if (-not $isAdmin) {
        Write-Error "Este script requiere privilegios de Administrador. Reejecutá PowerShell 'Run as Administrator'."
        exit 1
    }
}

Ensure-Admin

$ServiceName = 'PrintAgent'
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvPython = Join-Path $AgentDir 'venv\Scripts\python.exe'
$NssmDir = Join-Path $env:TEMP 'nssm'
$NssmZip = Join-Path $env:TEMP 'nssm.zip'
$NssmExe = Join-Path $NssmDir 'nssm.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Warning "No se encontró python en $VenvPython. Asegurate de haber creado el venv y haber instalado requirements."
}

if (-not (Test-Path $NssmExe)) {
    Write-Host "Descargando NSSM..."
    $urls = @( 
        'https://nssm.cc/release/nssm-2.24.zip',
        'https://github.com/kohsuke/nssm/releases/download/2.24/nssm-2.24.zip'
    )
    $got = $false
    foreach ($u in $urls) {
        try {
            Invoke-WebRequest -Uri $u -OutFile $NssmZip -UseBasicParsing -ErrorAction Stop
            Expand-Archive -Path $NssmZip -DestinationPath $NssmDir -Force
            # try to find nssm.exe inside extracted folder
            $found = Get-ChildItem -Path $NssmDir -Filter nssm.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { Move-Item -Path $found.FullName -Destination $NssmExe -Force }
            $got = $true; break
        } catch {
            Write-Warning "Fallo al descargar/extraer NSSM desde $u : $_"
        }
    }
    if (-not $got) {
        Write-Warning "No se pudo obtener NSSM automáticamente. Descargalo manualmente desde https://nssm.cc/ y colocá nssm.exe en $NssmDir"
        New-Item -ItemType Directory -Path $NssmDir -Force | Out-Null
    }
}

if (-not (Test-Path $NssmExe)) {
    Write-Error "No se encontró nssm.exe. Colocalo en: $NssmExe y reejecutá este script."
    exit 1
}

$ExeArgs = "-m uvicorn main:app --host 127.0.0.1 --port 34567"

Write-Host "Instalando servicio $ServiceName con NSSM..."
& $NssmExe install $ServiceName $VenvPython $ExeArgs
& $NssmExe set $ServiceName AppDirectory $AgentDir
& $NssmExe set $ServiceName Start SERVICE_AUTO_START

Write-Host "Arrancando servicio $ServiceName..."
& $NssmExe start $ServiceName

Write-Host "Servicio instalado y arrancado (si no hubo errores). Verificá con: Get-Service $ServiceName"
