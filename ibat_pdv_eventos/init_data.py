import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ibat_pdv_eventos.settings')
django.setup()

from django.contrib.auth.models import User
from pdv.models import Categoria, Evento, Producto, PuntoVenta

if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superusuario creado: admin / admin123')

evento, _ = Evento.objects.get_or_create(
    nombre='Evento de Prueba',
    defaults={'fecha': '2025-06-01', 'activo': True},
)
if _:
    print(f'Evento creado: {evento.nombre}')
else:
    evento.activo = True
    evento.save()
    print(f'Evento actualizado: {evento.nombre}')

categorias_data = ['Bebidas', 'Comidas', 'Postres', 'Snacks']
categorias = {}
for cat_nombre in categorias_data:
    cat, _ = Categoria.objects.get_or_create(nombre=cat_nombre, evento=evento)
    categorias[cat_nombre] = cat
    if _:
        print(f'Categoría creada: {cat_nombre}')

productos_data = [
    ('Agua mineral', 150.00, 21, 'Bebidas'),
    ('Gaseosa cola', 200.00, 21, 'Bebidas'),
    ('Gaseosa naranja', 200.00, 21, 'Bebidas'),
    ('Cerveza artesanal', 350.00, 21, 'Bebidas'),
    ('Limonada', 180.00, 21, 'Bebidas'),
    ('Hamburguesa simple', 500.00, 10.5, 'Comidas'),
    ('Hamburguesa completa', 650.00, 10.5, 'Comidas'),
    ('Papas fritas', 300.00, 10.5, 'Comidas'),
    ('Pancho', 350.00, 10.5, 'Comidas'),
    ('Empanada (x1)', 120.00, 10.5, 'Comidas'),
    ('Helado 1 bocha', 200.00, 10.5, 'Postres'),
    ('Flan con crema', 250.00, 10.5, 'Postres'),
    ('Brownie', 180.00, 10.5, 'Postres'),
    ('Alfajor', 100.00, 10.5, 'Snacks'),
    ('Papas fritas (paquete)', 80.00, 10.5, 'Snacks'),
    ('Maní', 100.00, 10.5, 'Snacks'),
    ('Chocolate', 120.00, 10.5, 'Snacks'),
]

for nombre, precio, impuesto, cat_nombre in productos_data:
    _, created = Producto.objects.get_or_create(
        nombre=nombre,
        evento=evento,
        defaults={
            'precio': precio,
            'tasa_impuesto': impuesto,
            'categoria': categorias[cat_nombre],
            'disponible': True,
        },
    )
    if created:
        print(f'Producto creado: {nombre}')

pdvs_data = [
    ('PDV 1 - Entrada', '192.168.0.58'),
    ('PDV 2 - Principal', '192.168.0.58'),
    ('PDV 3 - VIP', '192.168.0.58'),
]

for nombre, ip in pdvs_data:
    _, created = PuntoVenta.objects.get_or_create(
        nombre=nombre,
        evento=evento,
        defaults={'impresora_ip': ip},
    )
    if created:
        print(f'PDV creado: {nombre} ({ip})')

print('\nInicialización completada.')
print(f'Evento activo: {evento.nombre}')
print(f'Productos: {Producto.objects.filter(evento=evento).count()}')
print(f'Categorías: {Categoria.objects.filter(evento=evento).count()}')
print(f'PDVs: {PuntoVenta.objects.filter(evento=evento).count()}')
