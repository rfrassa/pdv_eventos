<#
.SYNOPSIS
    Genera un ZIP de emergencia para restaurar el servidor PDV en otra PC.
.DESCRIPTION
    Empaqueta el codigo fuente, la base de datos, los scripts de arranque
    y los paquetes pip pre-descargados (wheels/) para instalacion sin internet.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\crear_backup_emergencia.ps1
#>

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "`n[+] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    AVISO: $msg" -ForegroundColor Yellow }

$fecha   = Get-Date -Format "yyyy-MM-dd"
$zipName = "ibat_pdv_emergencia_$fecha.zip"
$zipPath = Join-Path $PSScriptRoot $zipName
$tempDir = Join-Path $env:TEMP "ibat_pdv_bak_temp"
$source  = $PSScriptRoot

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host " Backup de Emergencia - PDV Eventos" -ForegroundColor Magenta
Write-Host " Destino: $zipPath" -ForegroundColor Magenta
Write-Host "============================================"

# 1) Preparar directorio temporal
Write-Step "Preparando directorio temporal..."
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -ItemType Directory -Path $tempDir | Out-Null
Write-Ok $tempDir

# 2) Copiar archivos excluyendo venv, __pycache__, .git, staticfiles
Write-Step "Copiando archivos del proyecto (excluyendo venv, cache, .git)..."
$excludeDirs = @('venv', '__pycache__', '.git', 'staticfiles', '.claude', 'node_modules')
robocopy $source $tempDir /E /XD $excludeDirs /XF '*.pyc' '*.pyo' /NFL /NDL /NJH /NJS
# Robocopy usa codigos de salida como flags (0-7 = OK, 8+ = error real)
if ($LASTEXITCODE -ge 8) {
    Write-Warn "robocopy reporto codigo $LASTEXITCODE - verificar archivos copiados manualmente"
} else {
    Write-Ok "Copia completada (codigo robocopy: $LASTEXITCODE)"
}

# 3) Verificar que la base de datos esta incluida
Write-Step "Verificando base de datos..."
$dbPath = Join-Path $tempDir 'ibat_pdv_eventos\db.sqlite3'
if (Test-Path $dbPath) {
    $dbSize = [math]::Round((Get-Item $dbPath).Length / 1KB, 0)
    Write-Ok "db.sqlite3 incluida ($dbSize KB) - contiene todos los pedidos del evento"
} else {
    Write-Warn "No se encontro db.sqlite3 en la ruta esperada: $dbPath"
    Write-Warn "Verificar que la base de datos existe antes de distribuir este ZIP"
}

# 4) Descargar wheels pip para instalacion offline (usando pip freeze, no requirements.txt)
Write-Step "Descargando paquetes pip para instalacion offline (wheels/)..."
$wheelsDir  = Join-Path $tempDir 'wheels'
$frozenReqs = Join-Path $env:TEMP 'ibat_pdv_frozen_reqs.txt'
New-Item -ItemType Directory -Path $wheelsDir | Out-Null

$pipExe = Join-Path $source 'ibat_pdv_eventos\venv\Scripts\pip.exe'
if (-not (Test-Path $pipExe)) {
    $pipExe = (Get-Command pip -ErrorAction SilentlyContinue).Source
}

if ($pipExe) {
    # Usar pip freeze para obtener versiones EXACTAS instaladas (no requirements.txt que puede estar desactualizado)
    & $pipExe freeze | Out-File -FilePath $frozenReqs -Encoding UTF8
    Write-Host "    Descargando desde PyPI (requiere internet solo en ESTE paso)..." -ForegroundColor Gray
    & $pipExe download -r $frozenReqs -d $wheelsDir --quiet
    if ($LASTEXITCODE -eq 0) {
        $wheelCount = (Get-ChildItem $wheelsDir).Count
        $wheelsSize = [math]::Round((Get-ChildItem $wheelsDir | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
        Write-Ok "$wheelCount paquetes descargados ($wheelsSize MB) - instalacion offline disponible"
        Copy-Item $frozenReqs (Join-Path $tempDir 'ibat_pdv_eventos\requirements-frozen.txt')
    } else {
        Write-Warn "pip download termino con codigo $LASTEXITCODE - el ZIP no tendra instalacion offline"
    }
    Remove-Item $frozenReqs -ErrorAction SilentlyContinue
} else {
    Write-Warn "No se encontro pip - omitiendo wheels. El ZIP requerira internet."
}

# 5) Generar archivo de instrucciones de emergencia
Write-Step "Generando INSTRUCCIONES_EMERGENCIA.txt..."
$tieneWheels = (Test-Path $wheelsDir) -and ((Get-ChildItem $wheelsDir -ErrorAction SilentlyContinue).Count -gt 0)

$instrucciones = @"
RESTAURAR SERVIDOR DE EMERGENCIA - PDV Eventos
===============================================
Fecha del backup: $fecha

CONTENIDO DEL ZIP
-----------------
  - ibat_pdv_eventos/     codigo fuente + db.sqlite3
  - wheels/               paquetes pip pre-descargados (instalacion SIN internet)
  - iniciar_servidor.bat  arranque del servidor
  - INSTRUCCIONES_EMERGENCIA.txt  este archivo

REQUISITOS EN LA PC NUEVA
--------------------------
  1. Windows 10/11 (64-bit)
  2. Python 3.10 o superior con pip
     -> Si no tenes internet: usar python-3.xx-amd64.exe del pen drive
     -> Si tenes internet: https://www.python.org/downloads/
     IMPORTANTE: marcar "Add Python to PATH" durante la instalacion

  3. Google Chrome
     -> Si no tenes internet: usar ChromeSetup.exe del pen drive
     -> Si tenes internet: https://www.google.com/chrome/

PASOS DE RESTAURACION (~10 minutos)
------------------------------------
  1. Descomprimir este ZIP en C:\ibat_pdv_eventos

  2. Abrir PowerShell como Administrador y crear el entorno virtual:

       cd C:\ibat_pdv_eventos\ibat_pdv_eventos
       python -m venv venv
       venv\Scripts\activate

  3. Instalar dependencias:

     --- SIN internet (usar los wheels incluidos en el ZIP): ---
       pip install --no-index --find-links=..\wheels -r requirements-frozen.txt

     --- CON internet: ---
       pip install -r requirements-windows.txt

  4. Iniciar el servidor:

       cd C:\ibat_pdv_eventos
       iniciar_servidor.bat

  5. Verificar en el browser de esta PC:
       http://localhost:8000/

  6. Anotar la nueva IP (se muestra al arrancar) y actualizar los kiosks.

ACTUALIZAR IP EN PCs KIOSK
---------------------------
  Si la IP del servidor cambio, en cada PC kiosk ejecutar:

    powershell -ExecutionPolicy Bypass -File scripts\setup_pos_kiosk.ps1 -ServerUrl "http://[NUEVA_IP]:8000"

  O editar manualmente launch_kiosk_chrome.bat:
    Linea: set SERVER_URL=http://[NUEVA_IP]:8000/

QUE LLEVAR EN EL PEN DRIVE (prevencion)
----------------------------------------
  1. Este ZIP (ibat_pdv_emergencia_YYYY-MM-DD.zip)
  2. python-3.xx-amd64.exe    (bajar de python.org con anticipacion)
  3. ChromeSetup.exe           (bajar de google.com con anticipacion)
  El ZIP ya incluye wheels/ para no necesitar internet al instalar.

NOTAS
-----
  - db.sqlite3 tiene TODOS los pedidos del evento. Es el archivo mas critico.
  - El venv fue excluido del ZIP por tamano - se recrea con pip install.
  - Para reimprimir: Admin Django en http://[IP]:8000/admin/
  - Puerto por defecto: 8000. Si esta ocupado usa 8080, 8010, etc.

CONTACTO
--------
  rfrassa@gmail.com
"@

Set-Content -Path (Join-Path $tempDir 'INSTRUCCIONES_EMERGENCIA.txt') -Value $instrucciones -Encoding UTF8
Write-Ok "INSTRUCCIONES_EMERGENCIA.txt generado"

# 6) Crear el ZIP
Write-Step "Comprimiendo en $zipName..."
if (Test-Path $zipPath) {
    Write-Warn "Ya existe $zipPath - reemplazando"
    Remove-Item $zipPath
}
Compress-Archive -Path "$tempDir\*" -DestinationPath $zipPath -CompressionLevel Optimal
Write-Ok "ZIP creado"

# 7) Limpiar directorio temporal
Write-Step "Limpiando directorio temporal..."
Remove-Item $tempDir -Recurse -Force
Write-Ok "Limpieza completa"

# 8) Reporte final
$size = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " BACKUP COMPLETADO" -ForegroundColor Green
Write-Host " Archivo : $zipName" -ForegroundColor Green
Write-Host " Tamano  : $size MB" -ForegroundColor Green
Write-Host " Ruta    : $zipPath" -ForegroundColor Green
Write-Host " Offline : $(if ($tieneWheels) { 'SI - wheels incluidos' } else { 'NO - requiere internet' })" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Copia este archivo a un pen drive junto con:"
Write-Host "  - python-3.xx-amd64.exe  (instalador Python sin internet)"
Write-Host "  - ChromeSetup.exe        (instalador Chrome sin internet)"
Write-Host ""
