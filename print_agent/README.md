# Local Print Agent (PoC)

Pequeño agente HTTP para habilitar impresión silenciosa en la impresora por defecto del sistema.

Instalación rápida (Linux):

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/uvicorn main:app --host 127.0.0.1 --port 34567 &
```

Windows: instalar Python, crear venv, instalar requirements y ejecutar `uvicorn main:app --host 127.0.0.1 --port 34567`.

API endpoints:
- `GET /ping` - salud y nombre de impresora por defecto
- `GET /info` - info de plataforma/impresora
- `POST /print/raw` - enviar bytes raw a la impresora (application/octet-stream)
- `POST /print/html` - enviar HTML/text para impresión (text/html)
- `POST /pair` - guardar token de emparejamiento (form field `token`)

Notas:
- Este es un PoC. Para producción se debe endurecer seguridad, empaquetar como servicio, generar instalador y validar tipos MIME y conversiones (HTML->PDF).
