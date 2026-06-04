# STATE OF THE UNION — ibat_pdv_eventos

Ultima actualizacion: 2026-05-19

---

## 1. Proposito

Sistema POS para eventos (Pena IBAT 2026) con:
- PWA mobile (React-less, HTML+JS+CSS)
- Impresora termica POS-80C (192.168.0.58:9100) via TCP raw ESC/POS
- Tickets con split automatico: ticket cliente + comanda Comidas + comanda Bebidas
- Cierre de caja por PDV
- Descuentos, impuestos, multiples metodos de pago

---

## 2. Arquitectura

### 2.1 Entorno

| Componente | Detalle |
|---|---|
| Servidor | WSL2 (Ubuntu) O Windows 11 nativo |
| IP LAN servidor | 192.168.0.52 (Windows) |
| IP WSL | 172.20.252.60 |
| Puerto | 8000 |
| Base de datos | SQLite (`db.sqlite3`) |
| Mobile acceso | `http://192.168.0.52:8000` |
| Python | 3.x con venv en `/home/rafaelf/ibat_pdv_eventos/venv/` |
| Windows copy | `C:\ibat_pdv_eventos\` (copia manual de archivos) |

### 2.2 Estructura del proyecto

```
/home/rafaelf/ibat_pdv_eventos/
├── ibat_pdv_eventos/
│   ├── ibat_pdv_eventos/          # settings, urls root
│   ├── pdv/                       # app principal
│   │   ├── utils/
│   │   │   ├── local_printer.py   # EscposBuffer, TCP send, LocalPrinterService
│   │   │   ├── ticket_formatter.py# formateo de lineas de texto 48-col
│   │   │   └── ticket_handler.py  # orchestrator que usa LocalPrinterService
│   │   ├── views.py               # API views (@csrf_exempt en POST)
│   │   ├── urls.py                # routing (sin test_impresora)
│   │   ├── models.py
│   │   └── serializers.py
│   └── static/pwa/
│       ├── index.html
│       ├── app.js                 # keyboard nav en overlay de pago
│       ├── styles.css
│       ├── sw.js                  # service worker (cache v4)
│       └── manifest.json
├── scripts/
│   ├── iniciar_pdv.ps1
│   ├── iniciar_servidor.bat
│   └── setup_mobile_access.sh
└── venv/
```

---

## 3. Impresora POS-80C

### 3.1 Datos criticos

- **IP:** 192.168.0.58 | **Puerto:** 9100
- **Reset TCP:** Si no se envia data dentro de ~50ms de conectado, el printer cierra la conexion (`Connection reset by peer`)
- **Solucion:** `socket.connect()` + `socket.send()` inmediato, sin delays, sin handshakes
- **Encoding:** CP1252 forzado via `magic_encode_args={'encoding': 'CP1252'}` en `EscposBuffer`
- **No usar:** `PrinterService(Network(...))` de python-escpos, PowerShell `TcpClient`, ni GDI/CUPS

### 3.2 Flujo de impresion

```
app.js -> apiFetch('POST /api/pedidos/<id>/imprimir-local/')
  -> views.pedido_imprimir_local()
    -> LocalPrinterService.print_ticket(pedido)
      -> _print_escpos(lineas)           # Ticket principal (cliente)
      -> _print_escpos(lineas_comidas)   # solo si hay items en categoria Comidas
      -> _print_escpos(lineas_bebidas)   # solo si hay items en categoria Bebidas
        -> EscposBuffer.build() -> _enviar_tcp(data)
          -> socket.connect((IP, 9100)) + socket.send(data)
```

### 3.3 Codigo clave

| Archivo | Funcion |
|---|---|
| `local_printer.py:13-47` | `EscposBuffer` — captura ESC/POS en `bytearray` |
| `local_printer.py:50-61` | `_enviar_tcp(data)` — socket raw sin demoras |
| `local_printer.py:297-308` | `_print_escpos(lineas)` — construye y envia ESC/POS |
| `local_printer.py:357-374` | `print_ticket(pedido)` — orquesta split Comidas/Bebidas |
| `ticket_formatter.py:4` | `ANCHO_TICKEL = 48` — ancho de caracteres |
| `ticket_formatter.py:61-138` | `formatear()` — ticket cliente con precios/pagos |
| `ticket_formatter.py:36-59` | `formatear_comanda()` — comanda simple sin precios |

---

## 4. Endpoints API

| Ruta | Metodo | View | CSRF |
|---|---|---|---|
| `/` | GET | `pwa_index` | — |
| `/api/productos/` | GET/POST | `productos_list` | — |
| `/api/productos/<id>/` | GET/PATCH/DELETE | `producto_detail` | — |
| `/api/pedidos/` | POST | `pedido_create` | `@csrf_exempt` |
| `/api/pedidos/abiertos/` | GET | `pedidos_abiertos` | — |
| `/api/pedidos/historial/` | GET | `pedidos_historial` | — |
| `/api/pedidos/<id>/` | GET/PATCH/DELETE | `pedido_detail` | — |
| `/api/pedidos/<id>/reimprimir/` | POST | `pedido_reimprimir` | `@csrf_exempt` |
| `/api/pedidos/<id>/imprimir-local/` | POST | `pedido_imprimir_local` | `@csrf_exempt` |
| `/api/test-print/` | GET/POST | `test_print` | `@csrf_exempt` |
| `/api/cierre-caja/` | POST | `cierre_caja` | `@csrf_exempt` |
| `/api/pdv/` | GET | `pdvs_list` | — |

---

## 5. Estado de archivos (WSL vs Windows)

Todos modificados manualmente; **no hay sincronizacion automatica**. Lista de archivos que deben coincidir:

| Archivo | WSL | Windows |
|---|---|---|
| `pdv/views.py` | ✅ actual | ✅ actual |
| `pdv/urls.py` | ✅ actual | ✅ actual |
| `pdv/utils/local_printer.py` | ✅ actual | ✅ actual |
| `pdv/utils/ticket_handler.py` | ✅ actual | ✅ actual |
| `pdv/utils/ticket_formatter.py` | ✅ actual | ✅ actual |
| `static/pwa/app.js` | ✅ actual | ✅ actual |
| `static/pwa/sw.js` | ✅ actual | ✅ actual |

Todos los archivos estan copiados y verificados al 2026-05-19.

---

## 6. Reglas y restricciones

1. **No acentos/ñ** en tickets — reemplazar: Jose, Peña -> Pena, RaizDigital® -> RaizDigital
2. **No QR codes** en tickets (eliminados)
3. **Imprimir PC** es el unico trigger de impresion (no auto-print en creacion)
4. **TCP directo siempre** — sin GDI/CUPS/pywin32/lp para impresion real
5. **Keyboard nav** — Tab: Monto -> (Recibido si Efectivo) -> Agregar -> CONFIRMAR PAGO; Enter: ejecuta accion
6. **Service worker** — `CACHE_NAME` = `ibat-pdv-cache-v4`; si se modifica `app.js`, incrementar version
7. **Dos servidores** pueden coexistir (WSL + Windows) → cerrar el que no se usa
8. **Port forwarding** con `netsh` solo cuando Django corre en WSL; nativo en Windows no necesita

---

## 7. Comandos utiles

### Iniciar en Windows
```
C:\ibat_pdv_eventos\iniciar_servidor.bat
```
O doble clic en `C:\Users\Public\Desktop\iniciar_pdv.bat`

### Copiar archivos WSL -> Windows
```bash
cp /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/pdv/views.py /mnt/c/ibat_pdv_eventos/ibat_pdv_eventos/pdv/views.py
cp /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/pdv/urls.py /mnt/c/ibat_pdv_eventos/ibat_pdv_eventos/pdv/urls.py
cp /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/pdv/utils/local_printer.py /mnt/c/ibat_pdv_eventos/ibat_pdv_eventos/pdv/utils/local_printer.py
cp /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/pdv/utils/ticket_handler.py /mnt/c/ibat_pdv_eventos/ibat_pdv_eventos/pdv/utils/ticket_handler.py
cp /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/pdv/utils/ticket_formatter.py /mnt/c/ibat_pdv_eventos/ibat_pdv_eventos/pdv/utils/ticket_formatter.py
cp /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/static/pwa/app.js /mnt/c/ibat_pdv_eventos/ibat_pdv_eventos/static/pwa/app.js
cp /home/rafaelf/ibat_pdv_eventos/ibat_pdv_eventos/static/pwa/sw.js /mnt/c/ibat_pdv_eventos/ibat_pdv_eventos/static/pwa/sw.js
```

### Port forwarding (si corre en WSL)
```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 connectaddress=172.20.252.60 connectport=8000
```

### Test rapido de impresora (WSL)
```bash
python3 -c "
import socket
s = socket.socket()
s.settimeout(3)
s.connect(('192.168.0.58', 9100))
s.send(b'\x1b\x40\x1b\x74\x10Test OK\x0a\x1b\x64\x02\x1b\x69')
s.close()
print('OK')
"
```

---

## 8. Problemas conocidos / Pendientes

| # | Problema | Estado |
|---|---|---|
| 1 | PWA no actualiza `app.js` en mobile sin reinstalar/limpiar cache | Workaround: bump `CACHE_NAME` en `sw.js` |
| 2 | Dos servers pueden correr simultaneamente (WSL + Windows) | Atento: cerrar server viejo |
| 3 | Sin sincronizacion automatica WSL->Windows | Manual `cp` por ahora |
| 4 | `test_print` envia texto con "Jose" (acento en `views.py:182`) | Cosmetico, no afecta funcionalidad |
| 5 | `threading` import y `_imprimir_en_background` sin usar | Safe, mantenido para futuro |

---

## 9. Proximos pasos sugeridos

1. Agregar sync script (`cp` masivo) en `scripts/`
2. Mover Windows a correr Python nativo (sin WSL) permanentemente
3. Probar PWA desde iOS (Safari)
4. Agregar reconnect/reintento en `_enviar_tcp` si falla
5. Monitorear logs del server para detectar errores de impresion en vivo

---

## Actualizacion 2026-06-04 — Sesion de impresion PDV

### Realizado
- Impresion migrada a kiosk-printing del navegador (imprimirTicketNavegador + buildComandaHtml). Eliminada la dependencia del agente FastAPI y del path TCP.
- Mini PC cliente = solo Chrome con --kiosk-printing + impresora USB predeterminada. Sin Django local, sin agente.
- Servidor central: 192.168.0.59:8080 (waitress).
- Foco automatico en boton Confirmar Pago al cubrir el total.
- Comandas con items en 16pt bold (lectura sin anteojos).
- Endpoint /ticket-html/ creado pero NO en uso (path activo: imprimirTicketNavegador).
- Stock: seguimiento MANUAL via campo disponible (on/off). Sin conteo de cantidades.
- Fix: QuickEdit Mode de CMD congelaba el servidor; desactivar en Propiedades de la consola.
- Todo en origin/main. Tag de restauracion: estable-pre-evento.

### Pendiente (ventana de pruebas)
- DEBUG=False en settings.
- Evaluar PostgreSQL si hay varias cajas vendiendo en simultaneo (SQLite da "database is locked" bajo escritura concurrente).
- Servidor como servicio de Windows (NSSM): elimina la consola que se puede congelar.
- Verificar: comandas completas, cortes entre tickets, reimpresion usa el path nuevo.

### Backlog proximo evento
- Control de gestion de stock con cantidades (descuento automatico + alerta de agotado).
- Consolidar formatter: hay logica de ticket en Python (ticket_formatter.py) y en JS (buildTicketHtml). Unificar en una sola fuente.
- Limpiar worktrees viejos de agentes y archivos tmp_*.py.
