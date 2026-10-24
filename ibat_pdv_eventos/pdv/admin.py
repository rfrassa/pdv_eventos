from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db import transaction
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Categoria, Evento, LineaPedido, Pago, Pedido, Producto, PuntoVenta


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fecha', 'activo', 'cerrado_en']
    list_editable = ['activo']
    actions = ['cerrar_evento']

    @admin.action(description='Cerrar evento seleccionado', permissions=['change'])
    def cerrar_evento(self, request, queryset):
        """Cierra de a un evento: deja de aceptar pedidos y queda registrada la hora.
        No borra ni modifica ningún pedido. Reabrir = editar el evento (vaciar "Cerrado en")."""
        from .views import resumen_ventas  # import tardío: views importa modelos y serializers

        if queryset.count() != 1:
            self.message_user(request, 'Seleccioná un solo evento para cerrar.', messages.ERROR)
            return None
        evento = queryset.get()
        if evento.cerrado:
            self.message_user(request, f'"{evento.nombre}" ya está cerrado desde {timezone.localtime(evento.cerrado_en):%d/%m/%Y %H:%M}.', messages.WARNING)
            return None

        if request.POST.get('confirmar') != 'si':
            resumen = resumen_ventas(evento)
            return TemplateResponse(request, 'admin/pdv/evento/cerrar_evento.html', {
                **self.admin_site.each_context(request),
                'title': 'Cerrar evento',
                'opts': self.model._meta,
                'evento': evento,
                'resumen': resumen,
                'abiertos': Pedido.objects.filter(evento=evento, cerrado=False).count(),
                'hay_otros_activos': Evento.objects.filter(activo=True).exclude(pk=evento.pk).exists(),
                'action_checkbox_name': ACTION_CHECKBOX_NAME,
            })

        with transaction.atomic():
            cerrados = Evento.objects.filter(pk=evento.pk, cerrado_en__isnull=True).update(
                activo=False, cerrado_en=timezone.now())
        if not cerrados:
            self.message_user(request, f'"{evento.nombre}" ya se había cerrado.', messages.WARNING)
            return None
        self.message_user(request, format_html(
            'Evento "{}" cerrado. Descargar el resumen: <a href="{}?evento={}">Excel</a> · '
            '<a href="{}?evento={}" target="_blank">Versión para imprimir</a>',
            evento.nombre,
            reverse('resumen-ventas-xlsx'), evento.pk,
            reverse('resumen-ventas-imprimir'), evento.pk,
        ), messages.SUCCESS)
        return None


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
    list_display = ['id', 'evento', 'punto_venta', 'creado', 'cerrado', 'total_final']
    list_filter = ['evento', 'cerrado', 'punto_venta']
    inlines = [LineaPedidoInline, PagoInline]
