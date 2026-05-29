<#
Automated installer for Print Agent on Windows.
Run as Administrator from the `print_agent` directory.

This script will:
- create a Python virtualenv in `venv` (if missing)
- install requirements from `requirements.txt`
- download NSSM, extract `nssm.exe` to a temp folder
- register a Windows service `PrintAgent` that runs uvicorn
- start the service and enable auto-start

Usage (elevated PowerShell):
    .\install_windows_service_automated.ps1

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

$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $AgentDir

if (-not (Test-Path .\venv)) {
    Write-Host "Creando virtualenv..."
    python -m venv .\venv
}

Write-Host "Instalando dependencias..."
.\venv\Scripts\pip.exe install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt

$NssmDir = Join-Path $env:TEMP 'nssm_install'
New-Item -ItemType Directory -Path $NssmDir -Force | Out-Null
$NssmZip = Join-Path $NssmDir 'nssm.zip'
$NssmExe = Join-Path $NssmDir 'nssm.exe'

if (-not (Test-Path $NssmExe)) {
    Write-Host "Descargando NSSM..."
    $urls = @( 'https://nssm.cc/release/nssm-2.24.zip', 'https://github.com/kohsuke/nssm/releases/download/2.24/nssm-2.24.zip' )
    $got = $false
    foreach ($u in $urls) {
        try {
            Invoke-WebRequest -Uri $u -OutFile $NssmZip -UseBasicParsing -ErrorAction Stop
            Expand-Archive -Path $NssmZip -DestinationPath $NssmDir -Force
            $found = Get-ChildItem -Path $NssmDir -Filter nssm.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { Move-Item -Path $found.FullName -Destination $NssmExe -Force }
            $got = $true; break
        } catch {
            Write-Warning "Fallo al descargar/extraer NSSM desde $u : $_"
        }
    }
    if (-not $got) {
        Write-Warning "No se pudo obtener NSSM automáticamente. Descargalo manualmente desde https://nssm.cc/ y colocá nssm.exe en $NssmDir"
    }
}

if (-not (Test-Path $NssmExe)) {
    Write-Error "No se encontró nssm.exe en $NssmDir. Copialo manualmente y reejecuta el script."
    Pop-Location
    exit 1
}

$ServiceName = 'PrintAgent'
$VenvPython = Join-Path $AgentDir 'venv\Scripts\python.exe'
$ExeArgs = "-m uvicorn main:app --host 127.0.0.1 --port 34567"

Write-Host "Instalando servicio $ServiceName..."
& $NssmExe install $ServiceName $VenvPython $ExeArgs
& $NssmExe set $ServiceName AppDirectory $AgentDir
& $NssmExe set $ServiceName Start SERVICE_AUTO_START

Write-Host "Arrancando servicio $ServiceName..."
& $NssmExe start $ServiceName

Write-Host "Comprobando estado del servicio..."
Start-Sleep -Seconds 2
Get-Service $ServiceName | Format-Table -AutoSize

Pop-Location
Write-Host "Instalación finalizada. Si todo salió bien, el servicio arrancará automáticamente en cada inicio." -ForegroundColor Green
