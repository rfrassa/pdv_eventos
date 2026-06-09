import os
import sys
import shutil
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image

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

def ordenar_productos(cat_nombre, productos):
    if cat_nombre == 'Comidas':
        def clave(p):
            # Empanadas primero (por precio), resto después (por precio)
            es_empanada = 'empanada' in p.nombre.lower()
            return (0 if es_empanada else 1, int(p.precio))
        return sorted(productos, key=clave)
    if cat_nombre != 'Bebidas':
        return productos
    def clave(p):
        n = p.nombre.lower()
        if 'fernet' in n:
            # Agrupa Jarra y Vaso Fernet juntos, ordenados por nombre
            return (1, p.nombre.lower(), 0)
        elif n.startswith('vino'):
            # Vinos ordenados por precio ascendente
            return (2, '', int(p.precio))
        else:
            return (0, p.nombre.lower(), 0)
    return sorted(productos, key=clave)

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
for p in Producto.objects.filter(evento=evento, disponible=True).order_by('categoria__nombre', 'precio', 'nombre'):
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

# Crear carpeta de salida para Netlify (index.html + imágenes separadas)
site_dir = os.path.join(script_dir, 'precios_site')
os.makedirs(site_dir, exist_ok=True)

# Incrustar logo IBAT en el centro del QR (ERROR_CORRECT_H soporta hasta 30% tapado)
logo_ibat_path = os.path.join(script_dir, 'logo_ibat.png')
qr_pil = qr_img.convert('RGB')
if os.path.exists(logo_ibat_path):
    logo = Image.open(logo_ibat_path).convert('RGB')
    qr_w, qr_h = qr_pil.size
    logo_size = int(qr_w * 0.26)
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    pad = 8
    bloque = Image.new('RGB', (logo_size + pad * 2, logo_size + pad * 2), 'white')
    bloque.paste(logo, (pad, pad))
    bw, bh = bloque.size
    qr_pil.paste(bloque, ((qr_w - bw) // 2, (qr_h - bh) // 2))
    print("   Logo IBAT incrustado en el QR")

qr_path = os.path.join(site_dir, 'qr.png')
qr_pil.save(qr_path)
# También guardar copia suelta para imprimir
qr_print_path = os.path.join(script_dir, 'qr_precios.png')
qr_pil.save(qr_print_path)
print("   Guardado: qr.png")

# --- Logos (se copian a la carpeta, el HTML los referencia por nombre) ---
def copiar_imagen(origen, destino_nombre):
    src = os.path.join(script_dir, origen)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(site_dir, destino_nombre))
        return True
    return False

tiene_ibat = copiar_imagen('logo_ibat.png', 'logo_ibat.png')
tiene_cde  = copiar_imagen('logo_cde.png',  'logo_cde.png')
print("   Logo IBAT: " + ("copiado" if tiene_ibat else "no encontrado (logo_ibat.png)"))
print("   Logo CDE:  " + ("copiado" if tiene_cde  else "no encontrado (logo_cde.png)"))

# --- Paso 4: construir HTML ---
print("Paso 4/5: Generando HTML...")

secciones = ""
for cat_nombre, productos in grupos:
    items = ""
    for p in ordenar_productos(cat_nombre, productos):
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
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y54LRF62B0"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y54LRF62B0');
    </script>
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
            background: linear-gradient(160deg, #b02040 0%, #7a1c2e 50%, #2d0a14 100%);
            color: white;
            padding: 22px 20px 26px;
        }}
        .header-inner {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .logo-wrap {{
            background: white;
            border-radius: 10px;
            padding: 6px;
            box-shadow: 0 3px 12px rgba(0,0,0,0.35);
            flex-shrink: 0;
        }}
        .logo-wrap img {{
            width: 72px;
            height: 72px;
            object-fit: contain;
            display: block;
        }}
        .header-text {{
            flex: 1;
        }}
        .header-etiqueta {{
            font-size: 10px;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: #e8b86d;
            margin-bottom: 6px;
        }}
        header h1 {{
            font-size: 24px;
            font-weight: 800;
            line-height: 1.2;
        }}
        .header-fecha {{
            font-size: 13px;
            color: #f0d9a0;
            margin-top: 6px;
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
        <div class="header-inner">
            {('<div class="logo-wrap"><img src="logo_ibat.png" alt="IBAT San Jose"></div>') if tiene_ibat else ''}
            <div class="header-text">
                <div class="header-etiqueta">Lista de precios</div>
                <h1>{evento.nombre}</h1>
                <div class="header-fecha">{fecha_en_espanol(evento.fecha)}</div>
            </div>
            {('<div class="logo-wrap"><img src="logo_cde.png" alt="Centro de Estudiantes"></div>') if tiene_cde else ''}
        </div>
    </header>
    <main>
        {secciones}
    </main>
    <footer>
        <img src="qr.png" alt="QR">
        <div class="qr-label">Escaneá para ver los precios</div>
        <div class="qr-url">{URL_PRECIOS}</div>
    </footer>
    <div class="generado">Actualizado: {generado_en}</div>
</body>
</html>"""

html_path = os.path.join(site_dir, 'index.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("   Guardado: precios_site/index.html")

# --- Paso 5: resumen ---
print()
print("Paso 5/5: ¡Listo!")
print()
print("Archivos generados:")
print("  precios_site/           (carpeta entera -> arrastrar a Netlify)")
print("    index.html")
print("    qr.png")
print("    logo_ibat.png" if tiene_ibat else "    logo_ibat.png (falta)")
print("    logo_cde.png"  if tiene_cde  else "    logo_cde.png  (falta)")
print("  qr_precios.png          (copia para imprimir)")
print()
print("Para publicar en Netlify:")
print("  1. https://app.netlify.com > sitio existente > Deploys")
print("  2. Arrastrar la CARPETA precios_site/ completa a la zona de deploy")
print()
print("DNS (en el proveedor del dominio):")
print("  Tipo: CNAME  |  Nombre: precios  |  Valor: <sitio>.netlify.app")
