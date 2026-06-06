import os
import sys
import base64
from io import BytesIO
from datetime import datetime

# Verificar qrcode antes de arrancar Django
try:
    import qrcode
except ImportError:
    print("ERROR: La librería 'qrcode' no está instalada.")
    print("Ejecutá: pip install \"qrcode[pil]\"")
    sys.exit(1)

# Bootstrap Django (mismo patrón que init_data.py)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ibat_pdv_eventos.settings')
import django
django.setup()

from collections import defaultdict
from pdv.models import Evento, Producto

URL_PRECIOS = 'https://precios.ibatsanjose.edu.ar'

MESES = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
    5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
    9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
}

def formatear_precio(precio):
    entero = int(precio)
    return "$ " + f"{entero:,}".replace(",", ".")

def fecha_en_espanol(d):
    return f"{d.day} de {MESES[d.month]} de {d.year}"

print("=== GENERADOR DE PRECIOS - PEÑA 2026 ===")
print()

# --- Paso 1: evento activo ---
print("Paso 1/5: Buscando evento activo...")
try:
    evento = Evento.objects.get(activo=True)
except Evento.DoesNotExist:
    print("ERROR: No hay ningún evento marcado como activo.")
    print("Ir al admin (/admin/pdv/evento/) y marcar uno con activo=True.")
    sys.exit(1)
except Evento.MultipleObjectsReturned:
    print("ERROR: Hay más de un evento activo.")
    print("Ir al admin y dejar solo UNO con activo=True.")
    sys.exit(1)
print(f"   {evento.nombre}  —  {fecha_en_espanol(evento.fecha)}")

# --- Paso 2: productos ---
print("Paso 2/5: Cargando productos disponibles...")
# Agrupa por nombre de categoría directamente desde productos del evento.
# Esto funciona aunque las categorías estén asociadas a otro evento en la BD.
agrupado = defaultdict(list)
for p in Producto.objects.filter(evento=evento, disponible=True).order_by('categoria__nombre', 'nombre'):
    agrupado[p.categoria.nombre].append(p)
grupos = sorted(agrupado.items())

total = sum(len(p) for _, p in grupos)
print(f"   {total} productos en {len(grupos)} categorias")

if not grupos:
    print("ERROR: No hay productos disponibles para mostrar.")
    sys.exit(1)

# --- Paso 3: QR ---
print("Paso 3/5: Generando código QR...")
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=10,
    border=4,
)
qr.add_data(URL_PRECIOS)
qr.make(fit=True)
qr_img = qr.make_image(fill_color="black", back_color="white")

script_dir = os.path.dirname(os.path.abspath(__file__))

qr_path = os.path.join(script_dir, 'qr_precios.png')
qr_img.save(qr_path)
print(f"   Guardado: qr_precios.png")

buf = BytesIO()
qr_img.save(buf, format='PNG')
qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# --- Paso 4: construir HTML ---
print("Paso 4/5: Generando HTML...")

secciones = ""
for cat_nombre, productos in grupos:
    items = ""
    for p in productos:
        items += f"""
            <div class="item">
                <span class="item-nombre">{p.nombre}</span>
                <span class="item-precio">{formatear_precio(p.precio)}</span>
            </div>"""
    secciones += f"""
        <section class="categoria">
            <h2 class="cat-titulo">{cat_nombre.upper()}</h2>
            <div class="items">{items}
            </div>
        </section>"""

generado_en = datetime.now().strftime("%d/%m/%Y %H:%M")

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Precios — {evento.nombre}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f0eb;
            color: #2c1810;
            max-width: 600px;
            margin: 0 auto;
        }}
        header {{
            background: linear-gradient(135deg, #7a1c2e 0%, #4a0f1a 100%);
            color: white;
            text-align: center;
            padding: 32px 20px 28px;
        }}
        .header-etiqueta {{
            font-size: 11px;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: #e8b86d;
            margin-bottom: 10px;
        }}
        header h1 {{
            font-size: 26px;
            font-weight: 800;
            line-height: 1.2;
        }}
        .header-fecha {{
            font-size: 14px;
            color: #f0d9a0;
            margin-top: 8px;
        }}
        main {{
            padding: 16px 12px 24px;
        }}
        .categoria {{
            background: white;
            border-radius: 12px;
            margin-bottom: 14px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
        }}
        .cat-titulo {{
            background: #7a1c2e;
            color: #f0d9a0;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 2px;
            padding: 10px 16px;
        }}
        .items {{ padding: 4px 0; }}
        .item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            border-bottom: 1px solid #f0ebe5;
        }}
        .item:last-child {{ border-bottom: none; }}
        .item-nombre {{
            font-size: 15px;
            font-weight: 500;
            flex: 1;
        }}
        .item-precio {{
            font-size: 16px;
            font-weight: 700;
            color: #7a1c2e;
            margin-left: 12px;
            white-space: nowrap;
        }}
        footer {{
            background: white;
            border-top: 3px solid #7a1c2e;
            text-align: center;
            padding: 24px 20px 32px;
        }}
        footer img {{
            width: 150px;
            height: 150px;
            margin-bottom: 8px;
        }}
        .qr-label {{
            font-size: 13px;
            color: #555;
            margin-top: 4px;
        }}
        .qr-url {{
            font-size: 11px;
            color: #aaa;
            margin-top: 3px;
        }}
        .generado {{
            font-size: 10px;
            color: #ccc;
            text-align: center;
            padding: 12px;
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-etiqueta">Lista de precios</div>
        <h1>{evento.nombre}</h1>
        <div class="header-fecha">{fecha_en_espanol(evento.fecha)}</div>
    </header>
    <main>
        {secciones}
    </main>
    <footer>
        <img src="{qr_data_uri}" alt="QR">
        <div class="qr-label">Escaneá para ver los precios</div>
        <div class="qr-url">{URL_PRECIOS}</div>
    </footer>
    <div class="generado">Actualizado: {generado_en}</div>
</body>
</html>"""

html_path = os.path.join(script_dir, 'index.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"   Guardado: index.html")

# --- Paso 5: resumen ---
print()
print("Paso 5/5: ¡Listo!")
print()
print("Archivos generados:")
print(f"  index.html              (subir a Netlify)")
print(f"  qr_precios.png          (imprimir para el evento)")
print()
print("Para publicar en Netlify:")
print("  1. https://app.netlify.com > 'Add new site' > 'Deploy manually'")
print("  2. Arrastrar precios_pena_2026.html a la zona de deploy")
print("  3. 'Domain settings' > agregar dominio: precios.ibatsajose.edu.ar")
print()
print("DNS (en el proveedor del dominio):")
print("  Tipo: CNAME  |  Nombre: precios  |  Valor: <sitio>.netlify.app")
