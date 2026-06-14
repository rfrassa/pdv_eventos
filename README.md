# PDV Eventos

Sistema de punto de venta para eventos presenciales. Diseñado para funcionar en red local sin internet, con soporte para múltiples cajas, impresión de comandas y tickets, y cobro por distintos medios de pago.

---

## Características

- **Multi-caja**: varias tablets o notebooks operando simultáneamente contra el mismo servidor
- **PWA offline-capable**: el frontend funciona como aplicación instalable en el dispositivo
- **Impresión de comandas**: enrutamiento por categoría a distintas impresoras de cocina/barra
- **Medios de pago**: efectivo, tarjeta de crédito/débito, transferencia/QR, cuenta corriente
- **Dashboard en vivo**: resumen de ventas actualizado cada 7 segundos
- **Cierre de caja**: detalle de pagos y totales por punto de venta
- **Reporte de evento**: exportación completa a HTML y Excel (pedidos, líneas, ventas por hora, etc.)
- **Impresión local**: agente en cada caja para impresión silenciosa sin diálogos

---

## Stack

| Componente | Tecnología |
|---|---|
| Backend | Django 5.x + Django REST Framework |
| Base de datos | SQLite (WAL mode) |
| Frontend | PWA — JavaScript vanilla, sin frameworks |
| Servidor WSGI | Waitress (Windows) |
| Print agent | FastAPI + uvicorn |
| Reportes | openpyxl |

---

## Arquitectura de red

```
[ Servidor central ]  ←──── red local (Ethernet/WiFi) ────→  [ Cajas (tablets/notebooks) ]
  Django + SQLite                                                   Browser / PWA
  IP fija: 192.168.x.x:8000                                        print agent local
```

El servidor corre en una sola máquina. Las cajas solo necesitan un navegador apuntando a la IP del servidor. La impresión se hace localmente en cada caja mediante el print agent.

---

## Instalación

### Requisitos
- Python 3.11+
- Windows (el print agent usa `pywin32` para impresión nativa; el servidor puede correr en Linux/Mac)

### Pasos

```bash
# 1. Clonar
git clone https://github.com/rfrassa/pdv_eventos.git
cd pdv_eventos/ibat_pdv_eventos

# 2. Entorno virtual
python -m venv ../venv
../venv/Scripts/activate       # Windows
# source ../venv/bin/activate  # Linux/Mac

# 3. Dependencias
pip install -r requirements.txt

# 4. Configuración
copy .env.example .env
# Editar .env con los valores del entorno

# 5. Base de datos
python manage.py migrate

# 6. Datos iniciales (evento de prueba + productos de ejemplo)
python init_data.py

# 7. Servidor
python manage.py runserver 0.0.0.0:8000
```

Abrir `http://localhost:8000` en el navegador.

---

## Configuración (.env)

```env
# Generar con: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DJANGO_SECRET_KEY=tu-clave-secreta

# 0 en producción
DJANGO_DEBUG=1

# IP del servidor en la red del evento (la que usan las cajas para conectarse)
PDV_SERVER_IP=192.168.x.x
```

---

## Setup de un nuevo evento

1. Entrar al admin de Django (`http://servidor:8000/admin`, usuario `admin` / contraseña definida en `init_data.py`)
2. Crear un **Evento** con nombre y fecha, marcarlo como activo
3. Crear las **Categorías** (Bebidas, Comidas, etc.) con el sufijo de comanda correspondiente
4. Crear los **Puntos de Venta** con la IP de la impresora de cada caja
5. Cargar los **Productos** con precio y tasa de impuesto
6. (Opcional) Ejecutar `python generar_precios.py` para generar la página pública de precios con QR

Un solo evento puede estar activo a la vez. Al crear uno nuevo, desactivar el anterior desde el admin.

---

## Print agent (impresión local en cada caja)

El print agent es un microservicio FastAPI que corre en cada caja y recibe los tickets desde el servidor para imprimirlos en la impresora local sin diálogos.

```bash
cd print_agent
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 34567
```

En Windows se puede instalar como servicio con `install_windows.ps1`. Ver `print_agent/README.md` para detalles.

El emparejamiento se hace desde la configuración de la PWA (ícono de impresora en la barra superior).

---

## Reporte de evento

Al cierre del evento, genera HTML + Excel con todos los datos:

```bash
python generar_reporte_evento.py          # usa el evento activo
python generar_reporte_evento.py 3        # por ID de evento
```

Genera `reporte_<nombre>_<fecha>.html` y `.xlsx` con 10 hojas: resumen, métodos de pago, productos, categorías, PDV, ventas por hora, detalle de pedidos, líneas completas, sin ventas, notas especiales.

---

## Atajos de teclado (en caja)

| Tecla | Acción |
|---|---|
| `Alt+N` | Nuevo ticket |
| `Alt+C` | Abrir cobro |
| `Alt+G` | Guardar pedido abierto |
| `Alt+O` | Ver pendientes |
| `Alt+H` | Historial |
| `Alt+I` | Selector de impresora |
| `Alt+P` | Imprimir pedido actual |

**En el overlay de cobro:**

| Tecla | Acción |
|---|---|
| `1`–`6` | Seleccionar método de pago |
| `Enter` | Agregar pago / confirmar |
| `Ctrl+Backspace` | Limpiar pagos |
| `Esc` | Cerrar cobro |

---

## Scripts de utilidad

| Script | Descripción |
|---|---|
| `init_data.py` | Crea evento de prueba, categorías y productos de ejemplo |
| `generar_precios.py` | Genera página HTML pública de precios con QR |
| `generar_reporte_evento.py` | Exporta reporte completo del evento (HTML + Excel) |
| `run_server_local.py` | Arranca el servidor con Waitress (producción Windows) |

---

## Estructura del proyecto

```
ibat_pdv_eventos/
├── ibat_pdv_eventos/   # configuración Django (settings, urls)
├── pdv/                # app principal
│   ├── models.py       # Evento, Producto, Pedido, Pago, etc.
│   ├── views.py        # endpoints REST
│   └── utils/          # impresión, formato de tickets
├── static/pwa/         # frontend (PWA)
├── print_agent/        # microservicio de impresión local
└── .env.example        # variables de entorno requeridas
```

---

## Licencia

MIT
