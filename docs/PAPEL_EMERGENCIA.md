# PAPEL DE EMERGENCIA - PDV Eventos

Generado 2026-10-26. Rutas verificadas en esta PC (DESKTOP-VU8QOHU, IP Ethernet 192.168.0.200).

> Verificado con el servidor levantado (PID 12896, arrancado 26/10/2026 17:19): lo lanza`venv\Scripts\python.exe run_server_local.py --host 0.0.0.0 --port 8080` con directorio de trabajo `C:\ibat_pdv_eventos\ibat_pdv_eventos` (el python.exe hijo que ve netstat es el de Python311 base: es el redirector normal del venv).

Proyecto:  C:\ibat_pdv_eventos\ibat_pdv_eventos
Base activa: C:\ibat_pdv_eventos\ibat_pdv_eventos\db.sqlite3
Venv:      C:\ibat_pdv_eventos\ibat_pdv_eventos\venv  (Python 3.11.9)

## A) REINICIO DEL SERVIDOR (PowerShell)

1. Matar lo que sirva el 8080:

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { taskkill /F /PID $_.OwningProcess }
```

2. Relanzar (equivale al .bat; deja la ventana abierta):

```powershell
cd C:\ibat_pdv_eventos\ibat_pdv_eventos
$env:DJANGO_DEBUG="0"; $env:DJANGO_ALLOWED_HOSTS="*"; $env:PDV_SERVER_BIND="0.0.0.0"; $env:PDV_SERVER_PORT="8080"
.\venv\Scripts\python.exe run_server_local.py --host 0.0.0.0 --port 8080
```

Alternativa de un paso (abre ventana nueva): doble clic en
`C:\ibat_pdv_eventos\ibat_pdv_eventos\iniciar_servidor_eth_fijo.bat`

3. Verificar:

```powershell
netstat -ano | findstr ":8080"
```

## B) RESTAURAR BASE (pierde todo lo posterior al backup)

1. Parar el servidor (paso A.1). La base usa modo WAL (existen db.sqlite3-wal y -shm con datos recientes): guardar los TRES archivos antes de tocar nada:

```powershell
$s=Get-Date -Format yyyyMMdd_HHmm; Copy-Item "C:\ibat_pdv_eventos\ibat_pdv_eventos\db.sqlite3*" -Destination "C:\ibat_pdv_eventos\backups\" ; Rename-Item C:\ibat_pdv_eventos\backups\db.sqlite3 "db_antes_de_restaurar_$s.sqlite3"
```

2. Copiar el backup pedido sobre la base activa:

```powershell
Remove-Item C:\ibat_pdv_eventos\ibat_pdv_eventos\db.sqlite3-wal,C:\ibat_pdv_eventos\ibat_pdv_eventos\db.sqlite3-shm -ErrorAction SilentlyContinue
Copy-Item C:\ibat_pdv_eventos\backups\db_pre_reset_20260612_0746.sqlite3 C:\ibat_pdv_eventos\ibat_pdv_eventos\db.sqlite3 -Force
```

3. Relanzar con A.2.

CUIDADO: ese backup es de junio 2026 (233 KB; la base actual pesa 466 KB). Su esquema es anterior
al codigo actual y puede faltarle migraciones (no correr `migrate` sin revision explicita).
Backups mas recientes y compatibles, en `C:\ibat_pdv_eventos\ibat_pdv_eventos\`:
`db_pre_pruebas_20261024.sqlite3` (24/10 18:09), `db_pre_permisos_20261024_1328.sqlite3`.
Para usar uno de esos, reemplazar el nombre en el paso B.2 (cambia el origen y la carpeta).

