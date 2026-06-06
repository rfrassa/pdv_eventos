# Página de precios para un nuevo evento

Guía paso a paso para publicar la página de precios con QR para cada evento.

---

## 1. Preparar el evento en Django Admin

1. Ir a `/admin/pdv/evento/`
2. Crear el nuevo evento (nombre, fecha) y marcarlo como `activo = True`
3. Desactivar el evento anterior (`activo = False`)

> Solo puede haber **un evento activo** a la vez.

---

## 2. Crear las categorías

Ir a `/admin/pdv/categoria/` y crear las categorías asociadas al nuevo evento:

- `Bebidas`
- `Comidas`
- `Choripan` (u otras según el evento)

---

## 3. Cargar los productos

Ir a `/admin/pdv/producto/` y cargar cada producto con:

- Nombre
- Precio
- Categoría (del nuevo evento)
- Evento (el nuevo evento activo)
- `disponible = True`

---

## 4. Generar el HTML y el QR

Abrir PowerShell en `C:\ibat_pdv_eventos\ibat_pdv_eventos\` con el venv activo:

```powershell
.\venv\Scripts\Activate.ps1
python generar_precios.py
```

Esto genera dos archivos en la misma carpeta:
- `index.html` → página de precios lista para Netlify
- `qr_precios.png` → imagen del QR para imprimir en carteles/volantes

> Si es un evento nuevo con URL diferente, editar la línea `URL_PRECIOS` en `generar_precios.py` antes de correr el script.

---

## 5. Publicar en Netlify

**Primera vez (nuevo site):**

1. Ir a [app.netlify.com](https://app.netlify.com)
2. `Add new site` → `Deploy manually`
3. Arrastrar el archivo `index.html` a la zona de deploy
4. Netlify asigna una URL automática tipo `nombre-random.netlify.app`

**Actualizar un site existente:**

1. Entrar al site en Netlify
2. Ir a la pestaña `Deploys`
3. Arrastrar el nuevo `index.html` → reemplaza el contenido anterior

---

## 6. Configurar el dominio custom

### En Netlify:
1. `Site configuration` → `Domain management` → `Add custom domain`
2. Escribir el subdominio: ej. `precios.ibatsanjose.edu.ar`
3. Si pide verificación de propiedad, copiar el valor del registro TXT que muestra

### En Hostinger (DNS de `ibatsanjose.edu.ar`):
Agregar dos registros:

| Tipo | Nombre | Valor | TTL |
|------|--------|-------|-----|
| CNAME | `precios` | `nombre-del-site.netlify.app` | 3600 |
| TXT | `subdomain-owner-verification` | *(valor que da Netlify)* | 14400 |

---

## 7. Activar HTTPS

1. Esperar entre 15 y 60 minutos para que el DNS propague
2. Volver a Netlify → `Domain management` → hacer clic en **Verify DNS configuration**
3. Una vez verificado, Netlify emite el certificado SSL automáticamente

Podés verificar la propagación DNS en [dnschecker.org](https://dnschecker.org) buscando el subdominio tipo CNAME.

---

## 8. Verificar

- [ ] Abrir `https://precios.ibatsanjose.edu.ar` en el celular
- [ ] Escanear el QR con la cámara → debe abrir la misma URL
- [ ] Confirmar que aparecen todos los productos con precios correctos
- [ ] Confirmar que el candado HTTPS está activo

---

## Notas

- El script `generar_precios.py` lee siempre el **evento activo** de la BD. No hay que tocar el HTML a mano.
- Si cambia un precio, editar en el admin y volver al paso 4.
- Netlify free tier soporta sitios ilimitados y ~500.000 visitas/mes por sitio (100 GB de ancho de banda).
- Los logos del colegio y del centro de estudiantes se agregan al script cuando estén disponibles (`logo_ibat.png` y `logo_cde.png` en la misma carpeta que el script).
