<#
 start_kiosk_with_printer.ps1

 Busca una impresora por substring (por defecto 'TP-450'), la establece como
 impresora por defecto y lanza `launch_kiosk_chrome.bat` para abrir Chrome en
 modo kiosko con impresión automática.

 Uso (PowerShell como Administrador):
   powershell -ExecutionPolicy Bypass -File .\start_kiosk_with_printer.ps1 -PrinterNameSubstring "TP-450"

#>

param(
    [string]$PrinterNameSubstring = "TP-450"
)

function Abort($msg) {
    Write-Error $msg
    exit 1
}

Write-Host "Buscando impresoras en el sistema..."
try {
    $printers = Get-Printer -ErrorAction Stop
} catch {
    Abort "No se pudieron obtener impresoras. Ejecuta este script como Administrador y verifica que el módulo PrintManagement esté disponible."
}

if (-not $printers) { Abort "No se encontraron impresoras en este equipo." }

$match = $printers | Where-Object { $_.Name -like "*$PrinterNameSubstring*" } | Select-Object -First 1

if (-not $match) {
    Write-Host "No se encontró impresora que contenga: '$PrinterNameSubstring'"
    Write-Host "Impresoras disponibles:";
    $printers | ForEach-Object { Write-Host " - $($_.Name)" }
    $choice = Read-Host "Escribe el nombre exacto de la impresora para usar (ENTER para cancelar)"
    if ([string]::IsNullOrWhiteSpace($choice)) { Write-Host "Cancelado."; exit 1 }
    $match = $printers | Where-Object { $_.Name -eq $choice } | Select-Object -First 1
    if (-not $match) { Abort "Nombre de impresora no encontrado: $choice" }
}

Write-Host "Seleccionada impresora: $($match.Name)"
try {
    Set-Printer -Name $match.Name -IsDefault $true -ErrorAction Stop
    Write-Host "Impresora por defecto establecida a: $($match.Name)"
} catch {
    Abort "No se pudo establecer la impresora por defecto: $_"
}

Write-Host "Cerrando instancias de Chrome (si las hay)..."
Stop-Process -Name chrome -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

$batPath = "C:\ibat_pdv_eventos\launch_kiosk_chrome.bat"
if (-not (Test-Path $batPath)) {
    $batPath = Join-Path -Path (Get-Location) -ChildPath "launch_kiosk_chrome.bat"
}
if (-not (Test-Path $batPath)) { Abort "No se encontró launch_kiosk_chrome.bat en C:\ibat_pdv_eventos ni en la carpeta actual." }

Write-Host "Lanzando: $batPath"
Start-Process -FilePath $batPath

Write-Host "Script finalizado. Chrome debería abrirse en modo kiosko con impresion automatica."
