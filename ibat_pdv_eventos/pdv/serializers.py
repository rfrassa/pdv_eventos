from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import Categoria, LineaPedido, Pago, Pedido, Producto, PuntoVenta


def _calcular_totales(lineas_data, productos_map):
    """
    lineas_data  : list de dicts con 'producto' (instancia Producto), 'cantidad', 'nota'
    productos_map: {producto.id: Producto} — el caller lo trae en una sola query
    Retorna (subtotal, total_impuestos, total_final, lineas_enriquecidas)
    donde cada item de lineas_enriquecidas tiene 'precio_unitario' tomado de la DB.
    """
    subtotal = Decimal('0')
    total_impuestos = Decimal('0')
    lineas_enriquecidas = []
    for linea in lineas_data:
        producto = productos_map[linea['producto'].id]
        precio = producto.precio
        tasa = producto.tasa_impuesto
        cantidad = linea['cantidad']
        linea_subtotal = cantidad * precio
        linea_impuesto = linea_subtotal * tasa / Decimal('100')
        subtotal += linea_subtotal
        total_impuestos += linea_impuesto
        lineas_enriquecidas.append({
            'producto': producto,
            'cantidad': cantidad,
            'precio_unitario': precio,
            'nota': linea.get('nota', ''),
        })
    return subtotal, total_impuestos, subtotal + total_impuestos, lineas_enriquecidas


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre']


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'precio', 'tasa_impuesto', 'categoria', 'categoria_nombre', 'evento', 'disponible']
        read_only_fields = ['evento']

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a 0.')
        return value


class ProductoWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'precio', 'tasa_impuesto', 'categoria', 'evento', 'disponible']

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor a 0.')
        return value


class LineaPedidoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    categoria_nombre = serializers.CharField(source='producto.categoria.nombre', read_only=True)
    tasa_impuesto = serializers.DecimalField(source='producto.tasa_impuesto', max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = LineaPedido
        fields = ['id', 'producto', 'producto_nombre', 'categoria_nombre', 'cantidad', 'precio_unitario', 'nota', 'tasa_impuesto']

    def validate_cantidad(self, value):
        if value < 1:
            raise serializers.ValidationError('La cantidad mínima es 1.')
        return value


class LineaPedidoInputSerializer(serializers.Serializer):
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad = serializers.IntegerField(min_value=1)
    nota = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class PagoSerializer(serializers.ModelSerializer):
    metodo_display = serializers.CharField(source='get_metodo_display', read_only=True)

    class Meta:
        model = Pago
        fields = ['id', 'metodo', 'metodo_display', 'monto', 'monto_recibido']

    def validate_monto(self, value):
        if value <= 0:
            raise serializers.ValidationError('El monto debe ser mayor a 0.')
        return value


class PuntoVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PuntoVenta
        fields = ['id', 'nombre', 'impresora_ip']


class PedidoListSerializer(serializers.ModelSerializer):
    punto_venta_nombre = serializers.CharField(source='punto_venta.nombre', read_only=True)

    class Meta:
        model = Pedido
        fields = ['id', 'punto_venta', 'punto_venta_nombre', 'creado', 'cerrado', 'subtotal', 'descuento_porcentaje', 'total_impuestos', 'total_final', 'veces_impreso']


class PedidoDetailSerializer(serializers.ModelSerializer):
    lineas = LineaPedidoSerializer(many=True, read_only=True)
    pagos = PagoSerializer(many=True, read_only=True)
    punto_venta_nombre = serializers.CharField(source='punto_venta.nombre', read_only=True)

    class Meta:
        model = Pedido
        fields = ['id', 'punto_venta', 'punto_venta_nombre', 'creado', 'cerrado', 'subtotal', 'descuento_porcentaje', 'total_impuestos', 'total_final', 'lineas', 'pagos', 'veces_impreso']


class PedidoCreateSerializer(serializers.ModelSerializer):
    lineas = LineaPedidoInputSerializer(many=True)
    pagos = PagoSerializer(many=True, required=False, default=list)

    class Meta:
        model = Pedido
        fields = ['punto_venta', 'lineas', 'pagos']

    def validate(self, data):
        lineas_data = data.get('lineas', [])
        if not lineas_data:
            raise serializers.ValidationError('Debe incluir al menos una línea de pedido.')

        producto_ids = [l['producto'].id for l in lineas_data]
        productos_map = {p.id: p for p in Producto.objects.filter(id__in=producto_ids)}

        subtotal, total_impuestos, total_final, lineas_enriquecidas = _calcular_totales(lineas_data, productos_map)

        pagos = data.get('pagos', [])
        if pagos:
            total_pagos = sum(p['monto'] for p in pagos)
            if total_final != total_pagos:
                raise serializers.ValidationError(
                    f'La suma de los pagos (${total_pagos:.2f}) no coincide con el total (${total_final:.2f}).'
                )

        data['lineas'] = lineas_enriquecidas
        data['_subtotal'] = subtotal
        data['_total_impuestos'] = total_impuestos
        data['_total_final'] = total_final
        return data

    @transaction.atomic
    def create(self, validated_data):
        lineas_enriquecidas = validated_data.pop('lineas')
        pagos_data = validated_data.pop('pagos', [])
        subtotal = validated_data.pop('_subtotal')
        total_impuestos = validated_data.pop('_total_impuestos')
        total_final = validated_data.pop('_total_final')

        pedido = Pedido.objects.create(
            **validated_data,
            subtotal=subtotal,
            descuento_porcentaje=Decimal('0'),
            total_impuestos=total_impuestos,
            total_final=total_final,
        )
        for linea in lineas_enriquecidas:
            LineaPedido.objects.create(pedido=pedido, **linea)
        if pagos_data:
            for pago_data in pagos_data:
                Pago.objects.create(pedido=pedido, **pago_data)
            pedido.cerrado = True
            pedido.save(update_fields=['cerrado'])
        return pedido


class PedidoUpdateSerializer(serializers.ModelSerializer):
    lineas = LineaPedidoInputSerializer(many=True, required=False)

    class Meta:
        model = Pedido
        fields = ['lineas']

    def validate(self, data):
        lineas_data = data.get('lineas')
        if lineas_data is not None:
            if not lineas_data:
                raise serializers.ValidationError('Si se envían lineas, debe haber al menos una.')
            producto_ids = [l['producto'].id for l in lineas_data]
            productos_map = {p.id: p for p in Producto.objects.filter(id__in=producto_ids)}
            subtotal, total_impuestos, total_final, lineas_enriquecidas = _calcular_totales(lineas_data, productos_map)
            data['lineas'] = lineas_enriquecidas
            data['_subtotal'] = subtotal
            data['_total_impuestos'] = total_impuestos
            data['_total_final'] = total_final
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        if instance.cerrado:
            raise serializers.ValidationError('No se puede editar un pedido cerrado.')
        lineas_data = validated_data.pop('lineas', None)
        subtotal = validated_data.pop('_subtotal', None)
        total_impuestos = validated_data.pop('_total_impuestos', None)
        total_final = validated_data.pop('_total_final', None)

        if lineas_data is not None:
            instance.lineas.all().delete()
            for linea in lineas_data:
                LineaPedido.objects.create(pedido=instance, **linea)
            instance.subtotal = subtotal
            instance.total_impuestos = total_impuestos
            instance.total_final = total_final
            instance.descuento_porcentaje = Decimal('0')
            instance.save(update_fields=['subtotal', 'total_impuestos', 'total_final', 'descuento_porcentaje'])

        return instance
