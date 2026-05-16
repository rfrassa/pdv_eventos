import os
from django.conf import settings
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Evento, Pedido, Producto, PuntoVenta
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


@api_view(['POST'])
def pedido_create(request):
    serializer = PedidoCreateSerializer(data=request.data)
    if serializer.is_valid():
        pedido = serializer.save()
        try:
            from .utils.ticket_handler import imprimir_ticket
            imprimir_ticket(pedido)
        except Exception:
            pass
        return Response(PedidoDetailSerializer(pedido).data, status=status.HTTP_201_CREATED)
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


@api_view(['POST'])
def pedido_reimprimir(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
    try:
        from .utils.ticket_handler import imprimir_ticket
        imprimir_ticket(pedido)
        Pedido.objects.filter(id=pedido_id).update(veces_impreso=models.F('veces_impreso') + 1)
        return Response({'mensaje': 'Ticket reimpreso correctamente', 'veces_impreso': pedido.veces_impreso + 1})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cierre_caja(request):
    evento = get_object_or_404(Evento, activo=True)
    punto_venta_id = request.data.get('punto_venta_id')

    pedidos_qs = Pedido.objects.filter(
        punto_venta__evento=evento,
        cerrado=False,
    ).prefetch_related('pagos')
    if punto_venta_id:
        pedidos_qs = pedidos_qs.filter(punto_venta_id=punto_venta_id)

    resumen = {
        'evento': evento.nombre,
        'total_ventas': 0,
        'total_pedidos': pedidos_qs.count(),
        'total_por_metodo': {},
        'total_impuestos': 0,
        'pedidos': [],
    }

    for pedido in pedidos_qs:
        resumen['total_ventas'] += float(pedido.total_final)
        resumen['total_impuestos'] += float(pedido.total_impuestos)
        resumen['pedidos'].append({
            'id': pedido.id,
            'punto_venta': pedido.punto_venta.nombre,
            'total': float(pedido.total_final),
            'creado': pedido.creado.isoformat(),
        })
        for pago in pedido.pagos.all():
            metodo = pago.get_metodo_display()
            resumen['total_por_metodo'][metodo] = resumen['total_por_metodo'].get(metodo, 0) + float(pago.monto)
        pedido.cerrado = True
        pedido.save()

    resumen['total_ventas'] = round(resumen['total_ventas'], 2)
    resumen['total_impuestos'] = round(resumen['total_impuestos'], 2)
    return Response(resumen)


@api_view(['POST'])
def pedido_imprimir_local(request, pedido_id):
    pedido = get_object_or_404(Pedido.objects.select_related('punto_venta__evento').prefetch_related('lineas__producto', 'pagos'), id=pedido_id)
    printer_name = request.data.get('printer_name')
    try:
        from .utils.local_printer import LocalPrinterService
        service = LocalPrinterService(printer_name=printer_name)
        nombre = service.print_ticket(pedido)
        Pedido.objects.filter(id=pedido_id).update(veces_impreso=F('veces_impreso') + 1)
        return Response({'mensaje': f'Ticket enviado a {nombre}', 'impresora': nombre})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def impresoras_disponibles(request):
    try:
        from .utils.local_printer import LocalPrinterService
        service = LocalPrinterService()
        return Response({'impresoras': service.list_printers()})
    except Exception as e:
        return Response({'impresoras': [], 'error': str(e)})


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
