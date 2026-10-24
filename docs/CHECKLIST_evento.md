# CHECKLIST_evento — Puesta en marcha de un evento

> Creado en el ítem 5 de `plan_permisos.md` (no existía un checklist en el repo). Si ya tenés uno en otro
> lado, copiá ahí las secciones **2.3**, **3** y **4**, que son las nuevas por el login.

**Servidor:** puerto **8080** (`iniciar_servidor_dev.bat` o `iniciar_servidor_eth_fijo.bat`).
**Roles:** administrador = usuario con `is_staff`. Cajero = grupo `Cajero`, un usuario por caja (`caja1`, `caja2`, `caja3`).

---

## 1. Antes del evento (en la notebook del servidor, en el admin)
1. Backup de la base con el servidor **detenido**: copiar `db.sqlite3` (y `db.sqlite3-wal`/`-shm` si existen) a `db_pre_<motivo>_<fecha>.sqlite3`.
2. Evento nuevo creado y marcado como **activo** (solo uno activo a la vez; un evento cerrado no puede estar activo).
3. Categorías y productos cargados para ese evento.
4. Cajas (Puntos de Venta) creadas para el evento, con la IP de la impresora de cada una.
5. **Cada caja tiene su usuario cajero asignado:** Admin → Puntos de Venta → la caja → campo *Usuario cajero*. Un usuario no puede estar en dos cajas.
   - Si las cajas se reutilizan de un evento anterior, la asignación se mantiene. Verificar igual la columna *Usuario* en la lista.
6. Si se cambió algún archivo de `static/pwa/` (app.js, sw.js, index.html): correr `collectstatic` con el venv del servidor y subir `CACHE_NAME` en `sw.js`.

## 2. Por cada kiosco (cada caja)
1. Crear el perfil del navegador del kiosco y el acceso directo a `http://<IP-del-servidor>:8080/`.
2. Abrir la app. Si no hay sesión, aparece la pantalla de login.
3. **Login de la caja:** ingresar con el usuario de esa caja (`caja1`, `caja2` o `caja3`) y su contraseña.
   - La sesión dura **7 días** y sobrevive al reinicio del navegador. Si se borra el perfil del kiosco, hay que volver a hacer login.
4. Verificar que arriba a la derecha dice el nombre de **la caja correcta** (la caja sale del usuario; `?pdv=` no sirve para el cajero).
5. Elegir la impresora y hacer una venta de prueba: tiene que imprimir con el nombre de la caja en la comanda. Después borrar el pedido de prueba (si quedó sin cobrar) o dejarlo anotado.
6. El cajero **no** ve *Tablero* ni *Cambiar PDV*. Eso es lo esperado.

## 3. Si una caja dice "no tiene una caja asignada"
El usuario existe pero ninguna caja del evento activo lo tiene. Admin → Puntos de Venta → asignarle el usuario a la caja. Recargar el kiosco.

## 4. Contraseña olvidada de una caja
1. En el admin (`/admin/`), entrar como administrador → **Usuarios** → elegir `cajaN`.
2. En *Contraseña*, clic en el enlace **"este formulario"** y poner la nueva.
   - Alternativa por consola: `venv\Scripts\python.exe manage.py changepassword caja1`.
3. Al cambiar la contraseña se cierran las sesiones de ese usuario: el kiosco va solo al login. Entrar con la nueva.
4. Para crear los tres usuarios desde cero: `venv\Scripts\python.exe manage.py crear_cajeros` (pide las contraseñas por teclado; los que ya existen no se tocan).

## 5. Durante el evento
- El administrador entra a `http://<IP>:8080/` con su usuario para ver el **Tablero**, exportar el Excel o imprimir el resumen. Sin login no se descarga nada.
- Un pedido cobrado no se borra. Un cajero solo ve y borra pedidos sin cobrar **de su caja**.

## 6. Después del evento
1. Admin → Eventos → acción **"Cerrar evento seleccionado"** (confirma el total antes de cerrar).
2. Exportar el Excel final del evento desde el Tablero.
3. Backup de la base con el servidor detenido.
