from django.contrib import admin

from .models import Categoria, Evento, LineaPedido, Pago, Pedido, Producto, PuntoVenta


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fecha', 'activo']
    list_editable = ['activo']


@admin.register(PuntoVenta)
class PuntoVentaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'impresora_ip', 'evento']


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'evento', 'comanda_sufijo', 'comanda_etiqueta']
    list_editable = ['comanda_sufijo', 'comanda_etiqueta']


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'precio', 'categoria', 'evento', 'disponible']
    list_editable = ['disponible']
    list_filter = ['categoria', 'evento', 'disponible']


class LineaPedidoInline(admin.TabularInline):
    model = LineaPedido
    extra = 0


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ['id', 'punto_venta', 'creado', 'cerrado', 'total_final']
    list_filter = ['cerrado', 'punto_venta']
    inlines = [LineaPedidoInline, PagoInline]
