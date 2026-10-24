# plan_permisos.md — Permisos de administrador y cajero

**Proyecto:** `ibat_pdv_eventos` · repo `C:\ibat_pdv_eventos` · venv `C:\ibat_pdv_eventos\ibat_pdv_eventos\venv`
**Guardar en:** `C:\ibat_pdv_eventos\docs\plan_permisos.md` (versionado). Este archivo es el registro del avance.
**Ejecuta:** Claude Code · **Decide:** Rafael · **Autor de los commits:** Rafael Frassa, sin créditos para la IA.

## Reglas de ejecución
1. Un ítem por vez. Al terminar cada ítem: diff, tests y espera del OK de Rafael antes de commitear.
2. **Cada test se comprueba en las dos direcciones:** tiene que **fallar sin el cambio** y **pasar con el cambio**. Se anotan los dos resultados.
3. **Completar la columna "Resultado"** de cada test en este archivo: `✅ pasa` / `❌ falla`, más el commit, por ejemplo `✅ (falla sin cambio ✔) a1b2c3d`. Los tests manuales llevan fecha y quién los hizo. Este archivo se commitea junto con cada ítem.
4. Si un ítem cambia el esquema de datos: backup previo con el servidor detenido.
5. No dejar corriendo un servidor de producción desde la sesión de Claude Code. Para las pruebas, usar un servidor temporal, en otro puerto y con una copia de la base.

## Decisiones de Rafael (confirmar o cambiar antes del ítem 1)
| # | Decisión | Propuesta | Confirmado |
|---|---|---|---|
| D1 | Usuarios de caja | **Uno por caja** (`caja1`, `caja2`, `caja3`). Es lo más simple en el evento y no obliga a hacer login en cada cambio de turno. | ✅ 2026-10-24 |
| D2 | Cómo se asigna la caja | **La caja sale del usuario, no de la URL.** `?pdv=` deja de decidir. Así la caja 2 no puede vender como caja 1. | ✅ 2026-10-24 |
| D3 | Qué puede hacer el cajero | Cobrar, reimprimir, ver el historial **de su caja** y borrar pedidos **sin cobrar de su caja**. | ✅ 2026-10-24 |
| D4 | Qué es solo del administrador | El tablero de totales, el Excel y el imprimible, la lista de eventos, el cierre y el admin de Django. | ✅ 2026-10-24 |
| D5 | Duración de la sesión | **7 días.** La sesión no puede vencer en plena peña. Si se borra el perfil del kiosco, hay que volver a hacer login. | ✅ 2026-10-24 |

---

## Ítem 0 — Inventario (solo lectura, sin commit)
Reportar:
- Cada endpoint de `urls.py`: método HTTP, quién lo usa (kiosco, tablero o admin) y si cambia datos.
- La configuración actual de DRF en `settings.py` (autenticación y permisos por defecto).
- Cómo hace las llamadas `app.js` (`apiFetch`): cookies y headers.

Con eso se completa la matriz del ítem 2 **antes** de escribir código.

| Test | Esperado | Resultado |
|---|---|---|
| 0.1 | Tabla de endpoints completa, con columna "rol que lo necesita" | ✅ 2026-10-24 (Claude Code, revisado por Rafael) |

### Resultado del inventario (2026-10-24)
- DRF hoy: sin autenticación ni permisos; la API es pública. `SESSION_COOKIE_AGE` sin definir (default 2 semanas); no hay `LOGIN_URL`.
- `apiFetch` manda `X-CSRFToken` en todas las llamadas, sin `credentials` explícito (default `same-origin`) y sin distinguir 401/403.
- **`@csrf_exempt` en 5 vistas** (`pedido_create`, `pedido_reimprimir`, `test_print`, `cierre_caja`, `pedido_imprimir_local`): se quita en el ítem 2.
- Decisiones adicionales (Rafael, 2026-10-24): `/api/productos/` POST/PATCH/DELETE y `/api/test-print/` solo administrador. `/api/cierre-caja/` (POST que solo lee, sin uso en `app.js`) solo administrador; reabrir si la caja necesita su propio cierre.
- Los endpoints por `<id>` de pedidos hoy no verifican la caja; se resuelve en el ítem 3.
- Fuera de alcance: el agente de impresión local (`AGENT_URL`, `x-print-token`).

| Endpoint | Métodos | Rol |
|---|---|---|
| `/` | GET | público (sirve app y login) |
| `/api/productos/` | GET / POST | GET cajero o admin; POST admin |
| `/api/productos/<id>/` | GET / PATCH / DELETE | admin |
| `/api/pedidos/` | POST | cajero o admin (caja del usuario) |
| `/api/pedidos/abiertos/`, `/historial/` | GET | cajero o admin (filtrado por su caja) |
| `/api/pedidos/<id>/` | GET / PATCH / DELETE | cajero o admin, solo su caja |
| `/api/pedidos/<id>/reimprimir/`, `imprimir-local/` | POST | cajero o admin, solo su caja |
| `/api/pedidos/<id>/imprimir-pdf/`, `ticket-html/` | GET | cajero o admin, solo su caja |
| `/api/impresoras/`, `/api/pdv/` | GET | cajero o admin (`/pdv/` solo su caja) |
| `/api/test-print/`, `/api/cierre-caja/` | GET-POST / POST | admin |
| `/api/eventos/`, `/resumen-ventas/` (+ `xlsx`, `imprimir`) | GET | admin |
| `/admin/` | — | `is_staff` |

---

## Ítem 1 — Roles y usuarios de caja (cambia el esquema)
- **Rol administrador** = `is_staff`. **Rol cajero** = grupo `Cajero`.
- `PuntoVenta.usuario = OneToOneField(User, null=True, blank=True, on_delete=PROTECT)` (equivale a un FK único; evita el warning W342). Una caja tiene, como mucho, un usuario y un usuario no puede tener dos cajas.
- Comando `manage.py crear_cajeros`: crea `caja1`, `caja2` y `caja3` en el grupo `Cajero`, pide la contraseña por teclado y no la escribe en ningún archivo ni log. Se puede correr dos veces sin duplicar nada.

| Test | Esperado | Resultado |
|---|---|---|
| 1.1 | La migración aplica sobre una copia de la base, y los totales siguen en 812 / $13.662.000 y 216 / $1.435.000 | ✅ (sin cambio la columna `usuario_id` no existe ✔) copia en 0008, totales 812 / 13662000 y 216 / 1435000; base real intacta en 0007. 2026-10-24 |
| 1.2 | `crear_cajeros`, corrido dos veces, deja 3 usuarios y ninguno duplicado | ✅ (falla sin cambio ✔) `CajerosTests` |
| 1.3 | Un cajero no es staff y no puede entrar al admin | ✅ (falla sin cambio ✔) `CajerosTests` |
| 1.4 | Dos cajas no pueden tener el mismo usuario | ✅ (falla sin cambio ✔) `CajerosTests`; suite completa 36 OK |

---

## Ítem 2 — La API exige login, con permisos por rol
- DRF por defecto: `SessionAuthentication` + `IsAuthenticated`.
- Dos permisos: `EsCajeroOAdmin` y `EsAdmin`, aplicados según la matriz del ítem 0 y las decisiones D3 y D4.
- El Excel, el imprimible, `/api/resumen-ventas/` y `/api/eventos/` quedan **solo para el administrador**.

| Test | Esperado | Resultado |
|---|---|---|
| 2.1 | Sin login, **todos** los endpoints de la API devuelven 401 o 403 (recorriendo `urls.py`, no con una lista escrita a mano) | |
| 2.2 | Un cajero puede crear y cobrar pedidos y reimprimir | |
| 2.3 | Un cajero recibe 403 en el resumen, el Excel, el imprimible y la lista de eventos | |
| 2.4 | El administrador puede usar todo | |
| 2.5 | Un POST sin token CSRF, con sesión iniciada, se rechaza | |

---

## Ítem 3 — Cada cajero opera solo sobre su caja
- Al crear un pedido, `punto_venta` sale del usuario; si el cliente manda otro, se ignora. Un cajero sin caja asignada recibe 403 con un mensaje claro.
- El historial y los pedidos abiertos se filtran por la caja del cajero (el administrador ve todo).
- Un cajero solo puede borrar pedidos sin cobrar **de su caja**. Las reglas de pedidos cobrados y de eventos cerrados siguen igual.

| Test | Esperado | Resultado |
|---|---|---|
| 3.1 | `caja2` manda `punto_venta=5` y el pedido queda en la caja 6 | |
| 3.2 | `caja1` no ve el historial de la caja 2 | |
| 3.3 | `caja1` no puede borrar un pedido sin cobrar de la caja 2 (403) | |
| 3.4 | Un cajero sin caja asignada no puede crear pedidos (403 con mensaje) | |
| 3.5 | Siguen vigentes las reglas de pedidos cobrados y eventos cerrados (409) | |

---

## Ítem 4 — Login en el kiosco
- Una página de login simple, apta para pantalla táctil, que después de entrar vuelve a la app.
- `GET /api/me/` devuelve el usuario, el rol y la caja. El frontend toma la caja de ahí, no de `?pdv=`.
- `apiFetch` manda `X-CSRFToken` en los POST, PATCH y DELETE. Ante un 401 o 403 por sesión vencida, lleva al login **sin perder el carrito**.
- `SESSION_COOKIE_AGE` según D5. Sube `CACHE_NAME` y se ejecuta `collectstatic`.

| Test | Esperado | Resultado |
|---|---|---|
| 4.1 | `/api/me/` devuelve el rol y la caja correctos para `caja1` y para el administrador | |
| 4.2 | La sesión dura lo que dice D5 | |
| 4.3 (manual) | En el kiosco: login con `caja1`, venta mixta, salen 3 comandas con "Caja 1" | |
| 4.4 (manual) | Se reinicia el kiosco y sigue con la sesión iniciada | |
| 4.5 (manual) | Con la sesión vencida a propósito, va al login y al volver el carrito sigue | |

---

## Ítem 5 — Despliegue y checklist
- Backup, migración, `collectstatic` y `crear_cajeros`. Asignar las cajas en el admin.
- Actualizar `CHECKLIST_evento` con el paso **"login de la caja"** después de crear el perfil del kiosco, y cómo recuperar una contraseña olvidada desde el admin.

| Test | Esperado | Resultado |
|---|---|---|
| 5.1 (manual) | Las dos cajas físicas hacen login y venden, cada una con su nombre en la comanda | |
| 5.2 (manual) | Desde la notebook, sin login, `/api/resumen-ventas/xlsx/` no descarga nada | |
| 5.3 (manual) | El tablero y el Excel funcionan logueado como administrador | |
