# plan_impresoras.md — Cualquier impresora conectada al servidor (USB, red o Bluetooth), elegida desde cada dispositivo

**Proyecto:** `ibat_pdv_eventos` · repo `C:\ibat_pdv_eventos` · venv `C:\ibat_pdv_eventos\ibat_pdv_eventos\venv`
**Guardar en:** `C:\ibat_pdv_eventos\docs\plan_impresoras.md` (versionado).
**Ejecuta:** Claude Code · **Decide:** Rafael · **Autor de los commits:** Rafael Frassa, sin créditos para la IA.

## Reglas de ejecución
- Un ítem por vez, con diff y OK de Rafael antes de cada commit.
- Cada test tiene que fallar sin el cambio y pasar con el cambio. Se completa la columna **Resultado** (`✅ / ❌`, si falla sin el cambio, y el commit). Los manuales llevan fecha y equipo.
- Backup antes de cambiar el esquema de datos. No dejar corriendo un servidor de producción desde la sesión de Claude Code.

## El problema
Desde el celular se puede elegir una impresora, pero **la comanda sale por otra**, como si el destino estuviera escrito en el código. En la fase 1 de la Expo ya se había visto que existían un diccionario fijo `PDV_IMPRESORAS` y una IP de respaldo `192.168.0.67` en `local_printer.py`. **Primero hay que confirmar la causa (ítem 0)**; recién después se cambia algo.

## El modelo (decidido por Rafael)
**Todas las impresoras se conectan al servidor**, nunca a los celulares ni a las tablets. Los dispositivos solo eligen en qué impresora imprimir y el servidor manda el trabajo. Así:
- funciona igual desde PC, Android y iPhone;
- hay un único camino de impresión y un único log;
- no se instala nada en los dispositivos.

| Conexión al servidor | Cómo imprime el servidor |
|---|---|
| USB (cola de Windows) | `win32print`, RAW |
| Red (IP:9100) | socket |
| Bluetooth emparejado con el servidor | puerto COM saliente (`pyserial`) |

El servidor genera los bytes ESC/POS de las comandas en **un único lugar**, cualquiera sea la conexión.

**Limitación de Bluetooth:** el alcance desde el servidor es de pocos metros (unos 10 m, menos con paredes o gente). Si un puesto está lejos del servidor, conviene una **impresora de red** en ese puesto.

## Decisiones de Rafael (confirmar antes del ítem 1)
| # | Decisión | Propuesta | Confirmado |
|---|---|---|---|
| P1 | Prioridad del destino | **La impresora elegida en el dispositivo** le gana a la predeterminada de la caja. Si el dispositivo no eligió ninguna, se usa la de la caja. | ☑ Rafael 2026-10-24: durante un evento no hay tiempo de abrir el admin. |
| P2 | Qué impresoras puede elegir un cajero | Solo las **permitidas para su caja**, que se configuran en el admin. El administrador puede elegir cualquiera. | ☑ Rafael 2026-10-24: opción A. Recomendación: cada caja con su impresora y una de respaldo permitidas. |

---

## Ítem 0 — Diagnóstico de "va a otra impresora" (lectura y reproducción, sin commit)
1. Recorrer el flujo completo, desde el clic en "Cobrar" en el celular hasta que el servidor manda los bytes, y anotar **en qué punto se decide el destino** (archivo y línea).
2. Buscar en todo el repo destinos escritos en el código: IPs, nombres de cola como `POS-80C`, `PDV_IMPRESORAS`, IPs de respaldo y valores por defecto.
3. Reproducir el problema: elegir la impresora A en el celular, cobrar, y registrar en el log del servidor qué impresora se usó.
4. Explicar el caso de Epson iPrint: si salió por el camino del **navegador** (diálogo de impresión de Android), la elección la hizo Android y no el sistema. Con este plan, desde el celular no se imprime nunca por el navegador: siempre por el servidor.

| Test | Esperado | Resultado |
|---|---|---|
| 0.1 | Causa identificada, con archivo y línea, y el log de la reproducción | 🟡 Causa identificada por lectura (`app.js:778/1268/1286`, ver Hallazgos). Reproducción en vivo pendiente de Rafael. |
| 0.2 | Lista completa de destinos escritos en el código | ✅ 2026-10-24, tabla en Hallazgos |

### Hallazgos del ítem 0 (2026-10-24, lectura de código; sin cambios)
**Dónde se decide el destino hoy**
1. **Al cobrar desde el celular NO se usa el servidor.** `static/pwa/app.js:778` (`confirmarPago`) llama a `imprimirTicketNavegador()` (`app.js:1286`), que arma HTML y llama a `window.print()` en una ventana nueva (`openPrintWindow`, `app.js:1268`). **El destino lo elige el diálogo de impresión del navegador / Android**, no la app. Es la causa más probable de "elijo una y sale por otra" (y explica el caso de Epson iPrint).
2. **El selector de impresora es solo decorativo.** `state.printerName` / `localStorage['pdv_printer']` (`app.js:33, 272, 1078`) se guarda y se muestra, pero **ningún código lo envía al servidor**: `printer_name` solo lo lee `pedido_imprimir_local` (`views.py:499`) y nadie llama a ese endpoint, salvo el script `run_print_latest_pedido.ps1`. La lista que se ofrece (`/api/impresoras/`) son las colas de Windows **del servidor**, no las del celular.
3. **Camino del servidor (reimprimir):** `pedido_reimprimir` (`views.py:194`) → `ticket_handler.imprimir_ticket` → `ip_para_pdv()` (`local_printer.py:19-22`): usa `PuntoVenta.impresora_ip` y, si está vacío, el diccionario `PDV_IMPRESORAS` por **id** de caja (`PDV1/2/3` → `.58/.59/.60`). Ignora cualquier elección del dispositivo. Además `LocalPrinterService.__init__` (`local_printer.py:~189`) cae a `IP_IMPRESORA = 192.168.0.67` si no llega IP.
4. **Fallo silencioso:** `TicketHandler.imprimir` atrapa el error y devuelve `False`; `pedido_reimprimir` responde `ok: True` y suma `veces_impreso` aunque no haya impreso nada.
5. `_send_raw_data` devuelve el texto fijo `'POS-80C (ip:9100)'` como "nombre" de la impresora (`local_printer.py:241`), sea cual sea la real.
6. Código muerto: `_imprimir_en_background` (`views.py:79`) no se llama desde ningún lado.
7. Agente local (`print_agent/`, `AGENT_URL = 127.0.0.1:34567` y token en `app.js:190-193`): solo se usa para el indicador de estado; la impresión no lo usa. Además hay un token escrito en el JS público (deuda de seguridad, fuera de este plan).

**Destinos escritos en el código (0.2)**
| Archivo | Qué |
|---|---|
| `pdv/utils/local_printer.py:9` | `IP_IMPRESORA = '192.168.0.67'` (respaldo) |
| `pdv/utils/local_printer.py:12-16` | `PDV_IMPRESORAS` (`.58/.59/.60`) |
| `pdv/utils/local_printer.py:241` | nombre fijo `POS-80C` en el resultado |
| `pdv/utils/ticket_handler.py:16` | mensaje que menciona `PDV_IMPRESORAS` |
| `pdv/views.py:213` | `test_print` usa `192.168.0.58` por defecto |
| `init_data.py:68-70` | IP `192.168.1.100` de ejemplo |
| `run_*.ps1` (4 scripts en la raíz del proyecto, sin versionar) | `192.168.0.57` / `.58` |
Solo las 3 primeras filas y `views.py:213` afectan la impresión real.

**Falta para cerrar 0.1:** la reproducción (elegir A en el celular, cobrar y mirar el log). El log actual (`logs/pdv_servidor.log`) no tiene ninguna impresión registrada, lo que confirma el punto 1: **cobrar no pasa por el servidor, así que no deja rastro**. La prueba en vivo la hace Rafael con las impresoras reales.

---

## Ítem 1 — Ningún destino escrito en el código
- Eliminar `PDV_IMPRESORAS`, la IP de respaldo y cualquier otro destino escrito en el código. **Si no hay impresora configurada, la respuesta es un error claro** ("La caja X no tiene impresora asignada"), nunca un destino por defecto.
- **Cada impresión registra en el log** el pedido, la caja, la impresora (id y nombre), el tipo, el destino real y el resultado.

| Test | Esperado | Resultado |
|---|---|---|
| 1.1 | Un test recorre los `.py` y `.js` del repo y falla si encuentra una IP literal o el nombre de una cola fuera de las migraciones y los tests | |
| 1.2 | Una caja sin impresora devuelve el error claro y **no imprime en ninguna** | |
| 1.3 | El log de una impresión muestra la impresora y el destino real | |

---

## Ítem 2 — Elegir la impresora en cada dispositivo (cambia el esquema)
- En `PuntoVenta`: `impresora_predeterminada` (FK) e `impresoras_permitidas` (M2M), según P2.
- `GET /api/impresoras/`: devuelve las impresoras que el usuario puede elegir, con `id`, `nombre`, `tipo` y un `estado` rápido (en línea / sin respuesta / desconocido), con una espera máxima de 1 segundo por impresora.
- **Selector "Imprimir en:"** en la pantalla de la caja. La elección se guarda en el dispositivo (`localStorage`) y se muestra siempre a la vista, por ejemplo "Imprime en: Barra (red)".
- `POST /api/pedidos/{id}/imprimir/` recibe `impresora_id`. El servidor **lo valida** (que esté permitida y activa) y **usa exactamente esa**, según P1. Si no es válida, devuelve 400 con un mensaje claro; nunca cambia de impresora en silencio.

| Test | Esperado | Resultado |
|---|---|---|
| 2.1 | Con `impresora_id=A`, imprime en A aunque la predeterminada de la caja sea B | |
| 2.2 | Sin `impresora_id`, imprime en la predeterminada de la caja | |
| 2.3 | Un cajero que manda una impresora no permitida para su caja recibe 400 y no se imprime nada | |
| 2.4 | Una impresora inactiva no aparece en la lista y no se acepta | |
| 2.5 | La migración aplica sobre una copia de la base, los totales no cambian, y cada caja conserva la impresora que tenía como predeterminada | |
| 2.6 (manual) | En el celular se elige A y sale por A; se cambia a B y sale por B. Probado con una USB, una de red y una Bluetooth del servidor, desde Android y desde iPhone | |

---

## Ítem 3 — Bluetooth conectado al servidor
- Nuevo tipo `serie`, con `puerto_com` y `baudios` (por defecto 9600). Se manda con `pyserial`, que hay que agregar a `requirements-windows.txt`.
- Documentar en `docs/CHECKLIST_evento.md` cómo emparejar en Windows: *Configuración → Bluetooth → Más opciones → Puertos COM* para ver el **COM saliente**.
- Si el puerto está ocupado o no existe, devuelve un error claro.

| Test | Esperado | Resultado |
|---|---|---|
| 3.1 | Con `pyserial` simulado, se mandan exactamente los bytes ESC/POS de la comanda | |
| 3.2 | Un puerto COM inexistente devuelve un error claro y queda en el log | |
| 3.3 (manual) | Una impresora Bluetooth emparejada con el servidor imprime una comanda pedida desde el celular | |

---

## Ítem 4 — Probar impresoras y entender los errores
- Botón **"Probar"** en el selector: imprime una hoja corta con el nombre de la impresora, la caja, la fecha y la hora, y el texto "Ñandú — Choripán — ¡Peña!".
- Mensajes de error específicos según el tipo:

| Tipo | Error | Mensaje |
|---|---|---|
| Red | La IP no responde | "La impresora 192.168.0.67 no responde: revisá el cable o la IP" |
| USB / Windows | La cola está en error o pausada | Avisa que la cola está en error o pausada |
| Bluetooth | El COM está ocupado o no existe | Avisa que el puerto está ocupado o no existe |

| Test | Esperado | Resultado |
|---|---|---|
| 4.1 | Cada tipo de error devuelve su mensaje, con los fallos simulados | |
| 4.2 (manual) | "Probar" funciona con una impresora USB, una de red y una Bluetooth del servidor, desde un celular Android y desde un iPhone | |
