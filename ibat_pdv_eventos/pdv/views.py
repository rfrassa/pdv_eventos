import os
import threading
from django.conf import settings
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Evento, LineaPedido, Pago, Pedido, Producto, PuntoVenta
from .serializers import (
    PedidoCreateSerializer,
    PedidoDetailSerializer,
    PedidoListSerializer,
    PedidoUpdateSerializer,
    ProductoSerializer,
    ProductoWriteSerializer,
)


@api_view(['GET', 'POST'])
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


@csrf_exempt
@api_view(['POST'])
def pedido_create(request):
    serializer = PedidoCreateSerializer(data=request.data)
    if serializer.is_valid():
        pedido = serializer.save()
        data = PedidoDetailSerializer(pedido).data
        data['impresion'] = 'pendiente'
        return Response(data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def pedidos_abiertos(request):
    evento_activo = get_object_or_404(Evento, activo=True)
    punto_venta_id = request.query_params.get('punto_venta_id')
    pedidos = Pedido.objects.filter(
        cerrado=False,
        punto_venta__evento=evento_activo,
    )
    if punto_venta_id:
        pedidos = pedidos.filter(punto_venta_id=punto_venta_id)
    pedidos = pedidos.select_related('punto_venta')
    serializer = PedidoListSerializer(pedidos, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def pedidos_historial(request):
    evento_activo = get_object_or_404(Evento, activo=True)
    punto_venta_id = request.query_params.get('punto_venta_id')
    pagina = int(request.query_params.get('pagina', 1))
    limite = int(request.query_params.get('limite', 50))

    pedidos = Pedido.objects.filter(punto_venta__evento=evento_activo)
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
def pedido_detail(request, pedido_id):
    if request.method == 'GET':
        pedido = get_object_or_404(
            Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos'),
            id=pedido_id,
        )
        serializer = PedidoDetailSerializer(pedido)
        return Response(serializer.data)

    if request.method == 'DELETE':
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    pedido = get_object_or_404(Pedido, id=pedido_id, cerrado=False)
    serializer = PedidoUpdateSerializer(pedido, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(PedidoDetailSerializer(pedido).data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
def pedido_reimprimir(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
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


@csrf_exempt
@api_view(['GET', 'POST'])
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


def resumen_ventas(evento, punto_venta_id=None):
    """Agrega ventas cobradas (cerrado=True) usando el ORM. Fuente única de verdad
    compartida por cierre_caja y resumen_ventas_view."""
    filtro_pedido = {'punto_venta__evento': evento, 'cerrado': True}
    filtro_pago   = {'pedido__punto_venta__evento': evento, 'pedido__cerrado': True}
    filtro_linea  = {'pedido__punto_venta__evento': evento, 'pedido__cerrado': True}

    if punto_venta_id:
        filtro_pedido['punto_venta_id'] = punto_venta_id
        filtro_pago['pedido__punto_venta_id'] = punto_venta_id
        filtro_linea['pedido__punto_venta_id'] = punto_venta_id

    totales = Pedido.objects.filter(**filtro_pedido).aggregate(
        total=Sum('total_final'),
        impuestos=Sum('total_impuestos'),
    )
    total_general  = round(float(totales['total']   or 0), 2)
    total_impuestos = round(float(totales['impuestos'] or 0), 2)
    total_pedidos  = Pedido.objects.filter(**filtro_pedido).count()

    metodos_display = dict(Pago.METODOS)
    por_metodo = [
        {
            'metodo': row['metodo'],
            'metodo_display': metodos_display.get(row['metodo'], row['metodo']),
            'total': round(float(row['total']), 2),
        }
        for row in (
            Pago.objects.filter(**filtro_pago)
            .values('metodo')
            .annotate(total=Sum('monto'))
            .order_by('-total')
        )
    ]

    por_producto = [
        {
            'nombre': row['producto__nombre'],
            'unidades': row['unidades'],
        }
        for row in (
            LineaPedido.objects.filter(**filtro_linea)
            .values('producto__nombre')
            .annotate(unidades=Sum('cantidad'))
            .order_by('-unidades')
        )
    ]

    return {
        'evento': evento.nombre,
        'total_general': total_general,
        'total_impuestos': total_impuestos,
        'total_pedidos': total_pedidos,
        'total_por_metodo': por_metodo,
        'por_producto': por_producto,
    }


@csrf_exempt
@api_view(['POST'])
def cierre_caja(request):
    evento = get_object_or_404(Evento, activo=True)
    punto_venta_id = request.data.get('punto_venta_id')

    resumen = resumen_ventas(evento, punto_venta_id)

    # Lista detallada de pedidos: exclusiva del cierre, no del tablero
    filtro = {'punto_venta__evento': evento, 'cerrado': True}
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


@api_view(['GET'])
def resumen_ventas_view(request):
    evento = get_object_or_404(Evento, activo=True)
    punto_venta_id = request.query_params.get('punto_venta_id') or None
    return Response(resumen_ventas(evento, punto_venta_id))


@csrf_exempt
@api_view(['POST'])
def pedido_imprimir_local(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta__evento').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
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
def pedido_imprimir_pdf(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
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
def pedido_ticket_html(request, pedido_id):
    import html as htmllib
    pedido = get_object_or_404(
        Pedido.objects.select_related('punto_venta__evento')
                      .prefetch_related('lineas__producto__categoria', 'pagos'),
        id=pedido_id,
    )
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
def pdvs_list(request):
    evento_activo = get_object_or_404(Evento, activo=True)
    pdvs = PuntoVenta.objects.filter(evento=evento_activo)
    from .serializers import PuntoVentaSerializer
    serializer = PuntoVentaSerializer(pdvs, many=True)
    return Response(serializer.data)
