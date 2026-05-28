<#
Setup POS kiosk script
Usage examples:
  # Interactive: choose printer from list
  powershell -ExecutionPolicy Bypass -File .\scripts\setup_pos_kiosk.ps1 -ServerUrl "http://192.168.0.51:8080"

  # Non-interactive: set printer and server URL
  powershell -ExecutionPolicy Bypass -File .\scripts\setup_pos_kiosk.ps1 -PrinterName "POS-80C" -ServerUrl "http://192.168.0.51:8080" -AutoConfirm
#>

param(
    [string]$PrinterName = "",
    [string]$ServerUrl = "",
    [string]$ChromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    [switch]$AutoConfirm
)

function Test-IsAdmin {
    $current = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $current.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Write-Info($msg) { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red }

if (-not (Test-IsAdmin)) {
    Write-Warn "No se detectaron permisos de Administrador. Algunas operaciones pueden fallar. Ejecuta PowerShell como Administrador si surge un error."
}

# 1) List printers
Write-Info "Detectando impresoras en el sistema..."
$printers = @()
try {
    $printers = Get-Printer -ErrorAction Stop | Select-Object -Property Name,Default
} catch {
    # Fallback to WMI
    $printers = Get-WmiObject -Class Win32_Printer | Select-Object @{Name='Name';Expression={$_.Name}},@{Name='Default';Expression={$_.Default}}
}

if (-not $printers -or $printers.Count -eq 0) {
    Write-Err "No se encontraron impresoras en el sistema. Asegúrate que la impresora está conectada e instalala antes de ejecutar este script."
    exit 1
}

Write-Host "Impresoras encontradas:" -ForegroundColor Green
$idx = 1
$printers | ForEach-Object { Write-Host ("{0,2}) {1} {2}" -f $idx, $_.Name, ($_.Default -eq $true ? "(default)" : "")); $idx++ }

# 2) Choose printer
if ([string]::IsNullOrWhiteSpace($PrinterName)) {
    # Try auto-detect hints
    $hints = @('POS','80','58','TM-','EPSON TM','EPSON','POS-','Thermal')
    $match = $null
    foreach ($h in $hints) {
        $match = $printers | Where-Object { $_.Name -match [regex]::Escape($h) } | Select-Object -First 1
        if ($match) { break }
    }
    if ($match) {
        Write-Info "Se detectó impresora candidata: $($match.Name)"
        if (-not $AutoConfirm) {
            $ans = Read-Host "Usar '$($match.Name)' como impresora por defecto? (Y/n)"
            if ($ans -match '^[nN]') { $match = $null }
        }
        if ($match) { $PrinterName = $match.Name }
    }
}

if ([string]::IsNullOrWhiteSpace($PrinterName)) {
    if ($AutoConfirm) {
        Write-Err "No se especificó impresora y no se detectó candidate automáticamente. Use -PrinterName o ejecute interactivo.";
        exit 1
    }
    $choice = Read-Host "Ingresa el número de la impresora a usar como default (ej: 1) o deja vacío para cancelar"
    if (-not $choice) { Write-Err "Operación cancelada por el usuario."; exit 1 }
    if (-not ($choice -as [int])) { Write-Err "Entrada inválida."; exit 1 }
    $sel = [int]$choice
    if ($sel -lt 1 -or $sel -gt $printers.Count) { Write-Err "Índice fuera de rango."; exit 1 }
    $PrinterName = $printers[$sel - 1].Name
}

Write-Info "Fijando impresora por defecto: $PrinterName"
# 3) Set default printer
$setOk = $false
try {
    if (Get-Command -Name Set-DefaultPrinter -ErrorAction SilentlyContinue) {
        Set-DefaultPrinter -Name $PrinterName -ErrorAction Stop
        $setOk = $true
    } else {
        # Fallback to PrintUI
        $cmd = "rundll32 printui.dll,PrintUIEntry /y /n \"$PrinterName\""
        Write-Info "Ejecutando: $cmd"
        cmd.exe /c $cmd
        $setOk = $true
    }
} catch {
    Write-Warn "Fallo al fijar impresora usando método directo: $_. Exception. Intentando WMI..."
    try {
        $w = Get-WmiObject -Class Win32_Printer -Filter "Name='$PrinterName'"
        if ($w) { $w.SetDefaultPrinter(); $setOk = $true }
    } catch {
        Write-Err "No se pudo fijar la impresora por defecto: $_"
    }
}

if ($setOk) {
    Write-Info "Impresora por defecto establecida:"
    try { Get-Printer | Where-Object {$_.Default -eq $true} | Format-Table Name } catch { (Get-WmiObject -Class Win32_Printer | Where-Object {$_.Default -eq $true}).Name }
} else {
    Write-Warn "No se confirmó el cambio de impresora por defecto. Revisa privilegios o el nombre exacto."
}

# 4) Update launch_kiosk_chrome.bat if ServerUrl provided
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir '..')
$batPath = Join-Path $repoRoot 'launch_kiosk_chrome.bat'
if ($ServerUrl -and (Test-Path $batPath)) {
    Write-Info "Actualizando $batPath con SERVER_URL=$ServerUrl"
    $content = Get-Content $batPath -Raw
    if ($content -match 'set SERVER_URL=') {
        $newUrl = $ServerUrl
        if ($newUrl[-1] -ne '/') { $newUrl += '/' }
        $content2 = $content -replace '(?m)^set SERVER_URL=.*$', "set SERVER_URL=$newUrl"
        Set-Content -Path $batPath -Value $content2 -Encoding UTF8
        Write-Info "$batPath actualizado"
    } else {
        Write-Warn "No se encontró la variable SERVER_URL en $batPath; saltando actualización."
    }
} elseif ($ServerUrl) {
    Write-Warn "No se encontró $batPath para actualizar. Asegúrate de ejecutar el script dentro del repo."
}

# 5) Stop Chrome processes (in the current session)
Write-Info "Deteniendo procesos de Chrome (si existen)..."
try { Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1 } catch {}

# 6) Start Chrome with kiosk printing flags
if (-not (Test-Path $ChromePath)) {
    Write-Warn "Chrome no encontrado en $ChromePath. Edita el parámetro -ChromePath o instala Chrome."
} else {
    $args = @('--kiosk','--kiosk-printing','--no-first-run','--disable-infobars','--disable-session-crashed-bubble','--allow-running-insecure-content')
    if ($ServerUrl) { $args += $ServerUrl }
    Write-Info "Iniciando Chrome: $ChromePath $($args -join ' ')"
    Start-Process -FilePath $ChromePath -ArgumentList $args -WindowStyle Normal
    Start-Sleep -Seconds 2
}

# 7) Verification
Write-Info "Verificando proceso Chrome y flags (si está corriendo):"
try {
    Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Select-Object ProcessId,CommandLine | ForEach-Object { Write-Host "PID=$($_.ProcessId) CMD=$($_.CommandLine)" }
} catch { Write-Warn "No se pudo consultar procesos Chrome." }

Write-Info "Script finalizado. Prueba a imprimir desde la app (confirmar pago o presionar imprimir)."