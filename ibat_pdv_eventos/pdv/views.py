import os
import threading
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.conf import settings
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Evento, LineaPedido, Pago, Pedido, Producto, PuntoVenta
from .permisos import (
    CajeroLeeAdminEscribe, EsAdmin, EsCajeroOAdmin, caja_restringida, es_admin, es_cajero, exigir_pedido_de_su_caja,
)
from .serializers import (
    PedidoCreateSerializer,
    PedidoDetailSerializer,
    PedidoListSerializer,
    PedidoUpdateSerializer,
    ProductoSerializer,
    ProductoWriteSerializer,
)


@api_view(['GET', 'POST'])
@permission_classes([CajeroLeeAdminEscribe])
def productos_list(request):
    evento_activo = get_object_or_404(Evento, activo=True)

    if request.method == 'GET':
        productos = Producto.objects.filter(evento=evento_activo).select_related('categoria')
        solo_disponibles = request.query_params.get('disponibles', 'true').lower() == 'true'
        categoria_id = request.query_params.get('categoria_id')
        if solo_disponibles:
            productos = productos.filter(disponible=True)
        if categoria_id:
            productos = productos.filter(categoria_id=categoria_id)
        serializer = ProductoSerializer(productos, many=True)
        return Response(serializer.data)

    data = request.data.copy()
    if 'evento' not in data:
        data['evento'] = evento_activo.id
    serializer = ProductoWriteSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response(ProductoSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([EsAdmin])
def producto_detail(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'GET':
        serializer = ProductoSerializer(producto)
        return Response(serializer.data)

    if request.method == 'PATCH':
        serializer = ProductoWriteSerializer(producto, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ProductoSerializer(producto).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    producto.disponible = False
    producto.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


def _imprimir_en_background(pedido_id):
    import django
    django.setup()
    from .models import Pedido
    try:
        pedido = Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos').get(id=pedido_id)
        from .utils.ticket_handler import imprimir_ticket
        imprimir_ticket(pedido)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error imprimiendo pedido #{pedido_id}: {e}")


@api_view(['POST'])
@permission_classes([EsCajeroOAdmin])
def pedido_create(request):
    data = request.data.copy()
    caja = caja_restringida(request.user)
    if caja is not None and hasattr(data, 'items'):  # si no es un objeto, el serializer lo rechaza con 400
        data['punto_venta'] = caja.id  # la caja sale del usuario; lo que mande el cliente se ignora
    serializer = PedidoCreateSerializer(data=data)
    if serializer.is_valid():
        pedido = serializer.save()
        data = PedidoDetailSerializer(pedido).data
        data['impresion'] = 'pendiente'
        return Response(data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def pedidos_abiertos(request):
    evento_activo = get_object_or_404(Evento, activo=True)
    caja = caja_restringida(request.user)
    punto_venta_id = caja.id if caja else request.query_params.get('punto_venta_id')
    pedidos = Pedido.objects.filter(
        cerrado=False,
        evento=evento_activo,
    )
    if punto_venta_id:
        pedidos = pedidos.filter(punto_venta_id=punto_venta_id)
    pedidos = pedidos.select_related('punto_venta')
    serializer = PedidoListSerializer(pedidos, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def pedidos_historial(request):
    evento_activo = get_object_or_404(Evento, activo=True)
    caja = caja_restringida(request.user)
    punto_venta_id = caja.id if caja else request.query_params.get('punto_venta_id')
    pagina = int(request.query_params.get('pagina', 1))
    limite = int(request.query_params.get('limite', 50))

    pedidos = Pedido.objects.filter(evento=evento_activo)
    if punto_venta_id:
        pedidos = pedidos.filter(punto_venta_id=punto_venta_id)
    pedidos = pedidos.order_by('-creado')

    total = pedidos.count()
    inicio = (pagina - 1) * limite
    pedidos = pedidos[inicio:inicio + limite].select_related('punto_venta')

    serializer = PedidoListSerializer(pedidos, many=True)
    return Response({
        'total': total,
        'pagina': pagina,
        'limite': limite,
        'resultados': serializer.data,
    })


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([EsCajeroOAdmin])
def pedido_detail(request, pedido_id):
    if request.method == 'GET':
        pedido = get_object_or_404(
            Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos'),
            id=pedido_id,
        )
        exigir_pedido_de_su_caja(request.user, pedido)
        serializer = PedidoDetailSerializer(pedido)
        return Response(serializer.data)

    pedido = get_object_or_404(Pedido.objects.select_related('evento'), id=pedido_id)
    exigir_pedido_de_su_caja(request.user, pedido)
    if pedido.evento.cerrado:
        return Response(
            {'detail': f'El evento "{pedido.evento.nombre}" está cerrado; sus pedidos no se pueden modificar ni borrar.'},
            status=status.HTTP_409_CONFLICT,
        )

    if request.method == 'DELETE':
        if pedido.cerrado:
            # Un pedido cobrado es dinero registrado: si hay que anularlo, es un estado, no un borrado.
            return Response(
                {'detail': 'Un pedido cobrado no se puede borrar.'},
                status=status.HTTP_409_CONFLICT,
            )
        pedido.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if pedido.cerrado:
        return Response({'detail': 'No se puede editar un pedido cobrado.'}, status=status.HTTP_404_NOT_FOUND)
    serializer = PedidoUpdateSerializer(pedido, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(PedidoDetailSerializer(pedido).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([EsCajeroOAdmin])
def pedido_reimprimir(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
    exigir_pedido_de_su_caja(request.user, pedido)
    try:
        from .utils.ticket_handler import imprimir_ticket
        imprimir_ticket(pedido)
        Pedido.objects.filter(id=pedido_id).update(veces_impreso=F('veces_impreso') + 1)
        return Response({'ok': True, 'mensaje': 'Ticket reimpreso correctamente', 'veces_impreso': pedido.veces_impreso + 1})
    except RuntimeError as e:
        return Response({'ok': False, 'error': str(e)})
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f'Error inesperado reimprimir #{pedido_id}: {e}')
        return Response({'ok': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([EsAdmin])
def test_print(request):
    ip = request.data.get('ip') if request.method == 'POST' else request.query_params.get('ip', '192.168.0.58')
    puerto = int(request.data.get('puerto', 9100) if request.method == 'POST' else request.query_params.get('puerto', 9100))
    try:
        from pdv.utils.local_printer import EscposBuffer
        import socket
        buf = EscposBuffer()
        buf.set(align='center')
        buf.text('=== TEST DE IMPRESION ===\n')
        buf.text(f'IP: {ip}:{puerto}\n')
        buf.text('Colaborando con el IBAT\n')
        buf.text('Peña IBAT 2026\n\n')
        buf.set(align='left')
        buf.text('Si ves esto la impresora\n')
        buf.text('funciona correctamente!\n\n')
        buf.cut()
        data = buf.build()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((ip, puerto))
        sock.send(data)
        sock.close()
        return Response({'mensaje': f'Ticket de prueba enviado a {ip}:{puerto}', 'ok': True})
    except Exception as e:
        return Response({'error': str(e), 'ok': False}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _rango_utc(desde, hasta):
    """Fechas (date, inclusive ambas, en hora de Argentina) -> (inicio, fin_exclusivo)
    como datetimes con zona, que Django compara contra los UTC guardados."""
    tz = timezone.get_default_timezone()
    inicio = timezone.make_aware(datetime.combine(desde, time.min), tz) if desde else None
    fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min), tz) if hasta else None
    return inicio, fin


def _filtros_cobrados(evento, punto_venta_id, desde, hasta, prefijo=''):
    """Único lugar donde se define qué pedidos cuentan en un resumen. `prefijo`
    ('pedido__') lo reutiliza para pagos y líneas."""
    filtro = {prefijo + 'cerrado': True}
    if evento is not None:
        filtro[prefijo + 'evento'] = evento
    if punto_venta_id:
        filtro[prefijo + 'punto_venta_id'] = punto_venta_id
    inicio, fin = _rango_utc(desde, hasta)
    if inicio:
        filtro[prefijo + 'creado__gte'] = inicio
    if fin:
        filtro[prefijo + 'creado__lt'] = fin
    return filtro


def resumen_ventas(evento, punto_venta_id=None, desde=None, hasta=None, con_pedidos=False):
    """Agrega ventas cobradas (cerrado=True) usando el ORM. Fuente única de verdad
    de la pantalla, el XLSX y la versión imprimible, y de cierre_caja.

    evento=None => todos los eventos. desde/hasta: date en hora de Argentina,
    inclusive ambas. con_pedidos agrega el detalle de pedidos (solo para exportar)."""
    filtro_pedido = _filtros_cobrados(evento, punto_venta_id, desde, hasta)
    filtro_rel = _filtros_cobrados(evento, punto_venta_id, desde, hasta, 'pedido__')
    pedidos = Pedido.objects.filter(**filtro_pedido)

    totales = pedidos.aggregate(
        total=Sum('total_final'),
        impuestos=Sum('total_impuestos'),
        cantidad=Count('id'),
    )
    total_general = round(float(totales['total'] or 0), 2)
    total_impuestos = round(float(totales['impuestos'] or 0), 2)
    total_pedidos = totales['cantidad']

    metodos_display = dict(Pago.METODOS)
    por_metodo = [
        {
            'metodo': row['metodo'],
            'metodo_display': metodos_display.get(row['metodo'], row['metodo']),
            'total': round(float(row['total']), 2),
        }
        for row in (
            Pago.objects.filter(**filtro_rel)
            .values('metodo')
            .annotate(total=Sum('monto'))
            .order_by('-total')
        )
    ]

    por_producto = [
        {
            'nombre': row['producto__nombre'],
            'unidades': row['unidades'],
            'importe': round(float(row['importe']), 2),
        }
        for row in (
            LineaPedido.objects.filter(**filtro_rel)
            .values('producto__nombre')
            .annotate(
                unidades=Sum('cantidad'),
                importe=Sum(ExpressionWrapper(
                    F('cantidad') * F('precio_unitario'),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )),
            )
            .order_by('-unidades', 'producto__nombre')
        )
    ]

    pagos_por_caja = defaultdict(dict)
    for row in (
        Pago.objects.filter(**filtro_rel)
        .values('pedido__punto_venta_id', 'metodo')
        .annotate(total=Sum('monto'))
    ):
        pagos_por_caja[row['pedido__punto_venta_id']][row['metodo']] = round(float(row['total']), 2)
    por_caja = [
        {
            'punto_venta_id': row['punto_venta_id'],
            'nombre': row['punto_venta__nombre'],
            'pedidos': row['cantidad'],
            'total': round(float(row['total']), 2),
            'por_metodo': pagos_por_caja.get(row['punto_venta_id'], {}),
        }
        for row in (
            pedidos.values('punto_venta_id', 'punto_venta__nombre')
            .annotate(cantidad=Count('id'), total=Sum('total_final'))
            .order_by('punto_venta__nombre')
        )
    ]

    franjas = {}
    for creado, total in pedidos.values_list('creado', 'total_final'):
        local = timezone.localtime(creado)
        inicio = local.replace(minute=local.minute - local.minute % 15, second=0, microsecond=0)
        franja = franjas.setdefault(inicio, {'pedidos': 0, 'total': Decimal('0')})
        franja['pedidos'] += 1
        franja['total'] += total
    por_franja = [
        {'franja': f'{inicio:%d/%m %H:%M}', 'pedidos': v['pedidos'], 'total': round(float(v['total']), 2)}
        for inicio, v in sorted(franjas.items())
    ]

    resumen = {
        'evento': evento.nombre if evento is not None else 'Todos los eventos',
        'evento_id': evento.id if evento is not None else None,
        'desde': desde.isoformat() if desde else None,
        'hasta': hasta.isoformat() if hasta else None,
        'total_general': total_general,
        'total_impuestos': total_impuestos,
        'total_pedidos': total_pedidos,
        'ticket_promedio': round(total_general / total_pedidos, 2) if total_pedidos else 0,
        'unidades_total': sum(p['unidades'] for p in por_producto),
        'total_por_metodo': por_metodo,
        'por_producto': por_producto,
        'por_caja': por_caja,
        'por_franja': por_franja,
    }
    if con_pedidos:
        resumen['pedidos'] = [
            {
                'id': p.id,
                'creado': timezone.localtime(p.creado).replace(tzinfo=None),
                'evento': p.evento.nombre,
                'caja': p.punto_venta.nombre,
                'subtotal': float(p.subtotal),
                'impuestos': float(p.total_impuestos),
                'total': float(p.total_final),
                'pagos': ' / '.join(
                    f'{metodos_display.get(pg.metodo, pg.metodo)} {pg.monto:.2f}' for pg in p.pagos.all()
                ),
            }
            for p in pedidos.select_related('evento', 'punto_venta').prefetch_related('pagos').order_by('creado')
        ]
    return resumen


@api_view(['POST'])
@permission_classes([EsAdmin])
def cierre_caja(request):
    evento = get_object_or_404(Evento, activo=True)
    punto_venta_id = request.data.get('punto_venta_id')

    resumen = resumen_ventas(evento, punto_venta_id)

    # Lista detallada de pedidos: exclusiva del cierre, no del tablero
    filtro = {'evento': evento, 'cerrado': True}
    if punto_venta_id:
        filtro['punto_venta_id'] = punto_venta_id
    resumen['pedidos'] = [
        {
            'id': p.id,
            'punto_venta': p.punto_venta.nombre,
            'total': float(p.total_final),
            'creado': p.creado.isoformat(),
        }
        for p in Pedido.objects.filter(**filtro).select_related('punto_venta')
    ]
    resumen['total_ventas'] = resumen['total_general']  # compatibilidad con clientes anteriores
    return Response(resumen)


def _parse_fecha(valor, nombre):
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ValidationError({nombre: 'Fecha inválida; usar AAAA-MM-DD.'})


def _evento_por_defecto():
    """El evento activo; si no hay (p. ej. recién cerrado), el más reciente."""
    return (Evento.objects.filter(activo=True).order_by('-fecha', '-id').first()
            or Evento.objects.order_by('-fecha', '-id').first())


def _resumen_desde_request(request, con_pedidos=False):
    """Lee evento ('todos' | id | vacío = por defecto), desde, hasta y punto_venta_id
    de la query string y devuelve resumen_ventas(). Lo comparten las tres salidas."""
    params = request.query_params
    evento_param = params.get('evento')
    if evento_param == 'todos':
        evento = None
    elif evento_param:
        if not evento_param.isdigit():
            raise ValidationError({'evento': 'Debe ser un id o "todos".'})
        evento = get_object_or_404(Evento, id=int(evento_param))
    else:
        evento = _evento_por_defecto()
        if evento is None:
            raise NotFound('No hay eventos cargados.')

    pv = params.get('punto_venta_id') or None
    if pv and not pv.isdigit():
        raise ValidationError({'punto_venta_id': 'Debe ser un id.'})
    desde = _parse_fecha(params.get('desde'), 'desde')
    hasta = _parse_fecha(params.get('hasta'), 'hasta')
    if desde and hasta and desde > hasta:
        raise ValidationError({'desde': 'La fecha desde no puede ser posterior a hasta.'})
    return resumen_ventas(evento, pv, desde, hasta, con_pedidos=con_pedidos)


@api_view(['GET'])
@permission_classes([EsAdmin])
def eventos_list(request):
    eventos = Evento.objects.order_by('-fecha', '-id')
    default = _evento_por_defecto()
    return Response([
        {'id': e.id, 'nombre': e.nombre, 'fecha': e.fecha.isoformat(), 'activo': e.activo,
         'cerrado_en': timezone.localtime(e.cerrado_en).isoformat() if e.cerrado_en else None,
         'por_defecto': default is not None and e.id == default.id}
        for e in eventos
    ])


@api_view(['GET'])
@permission_classes([EsAdmin])
def resumen_ventas_view(request):
    return Response(_resumen_desde_request(request))


@api_view(['GET'])
@permission_classes([EsAdmin])
def resumen_ventas_xlsx(request):
    from .reportes import nombre_archivo, resumen_a_xlsx
    resumen = _resumen_desde_request(request, con_pedidos=True)
    resp = HttpResponse(
        resumen_a_xlsx(resumen),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="{nombre_archivo(resumen, "xlsx")}"'
    return resp


@api_view(['GET'])
@permission_classes([EsAdmin])
def resumen_ventas_imprimir(request):
    resumen = _resumen_desde_request(request)
    return render(request._request, 'pdv/resumen_imprimible.html', {
        'r': resumen,
        'generado': timezone.localtime(),
    })


@api_view(['POST'])
@permission_classes([EsCajeroOAdmin])
def pedido_imprimir_local(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta__evento').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
    exigir_pedido_de_su_caja(request.user, pedido)
    printer_name = request.data.get('printer_name')
    try:
        from .utils.local_printer import LocalPrinterService, ip_para_pdv
        service = LocalPrinterService(ip=ip_para_pdv(pedido.punto_venta), printer_name=printer_name)
        nombre = service.print_ticket(pedido)
        Pedido.objects.filter(id=pedido_id).update(veces_impreso=F('veces_impreso') + 1)
        return Response({'ok': True, 'mensaje': f'Ticket enviado a {nombre}', 'impresora': nombre})
    except RuntimeError as e:
        return Response({'ok': False, 'error': str(e)})
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f'Error inesperado imprimir_local #{pedido_id}: {e}')
        return Response({'ok': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def pedido_imprimir_pdf(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
    exigir_pedido_de_su_caja(request.user, pedido)
    try:
        from .utils.ticket_formatter import TicketFormatter
        formatter = TicketFormatter()
        lineas = formatter.formatear(pedido)

        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm
            from io import BytesIO

            page_width = 80 * mm
            line_height = 12
            margin_top = 8
            height = max(200, int(margin_top + len(lineas) * line_height + 20))

            buf = BytesIO()
            c = canvas.Canvas(buf, pagesize=(page_width, height))
            c.setFont('Helvetica', 10)
            y = height - margin_top
            for l in lineas:
                c.drawString(6, y, l)
                y -= line_height
                if y < 10:
                    c.showPage()
                    c.setFont('Helvetica', 10)
                    y = height - margin_top
            c.showPage()
            c.save()
            buf.seek(0)
            resp = HttpResponse(buf.read(), content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="pedido-{pedido.id}.pdf"'
            return resp
        except ImportError:
            html_lines = '\n'.join(f"<div>{l}</div>" for l in lineas)
            html = f"""<html><head><meta charset='utf-8'><style>
                body{{font-family:monospace;width:80mm;margin:0;padding:8px}}
                </style></head><body>{html_lines}</body></html>"""
            return HttpResponse(html, content_type='text/html')

    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f'Error generando PDF #{pedido_id}: {e}')
        return Response({'ok': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def pedido_ticket_html(request, pedido_id):
    import html as htmllib
    pedido = get_object_or_404(
        Pedido.objects.select_related('punto_venta__evento')
                      .prefetch_related('lineas__producto__categoria', 'pagos'),
        id=pedido_id,
    )
    exigir_pedido_de_su_caja(request.user, pedido)
    from .utils.ticket_formatter import TicketFormatter
    formatter = TicketFormatter()

    def segs_a_html(segs):
        out = []
        for seg in segs:
            t = seg.texto
            if len(t) >= 4 and t.replace('=', '') == '':
                out.append('<hr class="thick">'); continue
            if len(t) >= 4 and t.replace('-', '') == '':
                out.append('<hr class="thin">');  continue
            if not t.strip():
                out.append('<p class="spacer"> </p>'); continue
            cls = []
            if seg.doble_alto and seg.negrita: cls.append('hdr-xl')
            elif seg.negrita:                  cls.append('hdr')
            if   seg.alinear == 'center':      cls.append('center')
            elif seg.alinear == 'right':       cls.append('right')
            attr = f' class="{" ".join(cls)}"' if cls else ''
            out.append(f'<p{attr}>{htmllib.escape(t)}</p>')
        return '\n'.join(out)

    secciones = []
    main_segs = formatter.formatear(pedido)
    if main_segs:
        secciones.append(segs_a_html(main_segs))

    cats = {l.producto.categoria.nombre for l in pedido.lineas.all()}
    for cat, etiqueta, sufijo in [('Comidas', 'COMIDAS', 'C'), ('Bebidas', 'BEBIDAS', 'B'), ('Choripan', 'CHORIPAN', 'CH')]:
        if cat in cats:
            segs = formatter.formatear_comanda(pedido, cat, etiqueta, sufijo)
            if segs:
                secciones.append(segs_a_html(segs))

    PB = '<div style="page-break-after:always"></div>'
    body = f'\n{PB}\n'.join(secciones)

    css = (
        '@page{size:80mm auto;margin:0}'
        'body{width:80mm;font-family:"Courier New",Courier,monospace;font-size:9pt;margin:0;padding:2mm 3mm}'
        'p{margin:0;line-height:1.3;white-space:pre-wrap}'
        '.hdr-xl{font-size:12pt;font-weight:bold;text-align:center;white-space:normal}'
        '.hdr{font-weight:bold}'
        '.center{text-align:center;white-space:normal}'
        '.right{text-align:right;white-space:normal}'
        'hr.thin{border:none;border-top:1px solid #000;margin:.5mm 0}'
        'hr.thick{border:none;border-top:2px solid #000;margin:.5mm 0}'
        '.spacer{line-height:3mm}'
    )
    html_doc = (
        f'<!DOCTYPE html><html><head><meta charset="utf-8">'
        f'<style>{css}</style></head><body>{body}</body></html>'
    )
    return HttpResponse(html_doc, content_type='text/html; charset=utf-8')


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def impresoras_disponibles(request):
    try:
        from .utils.local_printer import LocalPrinterService
        service = LocalPrinterService()
        return Response({'impresoras': service.list_printers()})
    except Exception as e:
        return Response({'impresoras': [], 'error': str(e)})


@ensure_csrf_cookie
def pwa_index(request):
    path = os.path.join(settings.BASE_DIR, 'static', 'pwa', 'index.html')
    with open(path, 'r', encoding='utf-8') as f:
        return HttpResponse(f.read())


@api_view(['GET'])
@permission_classes([EsCajeroOAdmin])
def pdvs_list(request):
    evento_activo = get_object_or_404(Evento, activo=True)
    pdvs = PuntoVenta.objects.filter(evento=evento_activo)
    caja = caja_restringida(request.user)
    if caja is not None:
        pdvs = pdvs.filter(id=caja.id)
    from .serializers import PuntoVentaSerializer
    serializer = PuntoVentaSerializer(pdvs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])  # a propósito sin rol: el frontend usa esto para explicarle al usuario sin rol por qué no puede operar
def me(request):
    user = request.user
    caja = None
    if es_admin(user):
        rol = 'admin'
    elif es_cajero(user):
        rol = 'cajero'
        caja = PuntoVenta.objects.filter(usuario=user).first()
    else:
        rol = None
    return Response({
        'username': user.get_username(),
        'rol': rol,
        'caja': {'id': caja.id, 'nombre': caja.nombre} if caja else None,
    })
