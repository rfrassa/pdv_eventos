from rest_framework import serializers

from .models import Categoria, LineaPedido, Pago, Pedido, Producto, PuntoVenta


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
    lineas = LineaPedidoSerializer(many=True)
    pagos = PagoSerializer(many=True)

    class Meta:
        model = Pedido
        fields = ['punto_venta', 'subtotal', 'descuento_porcentaje', 'total_impuestos', 'total_final', 'lineas', 'pagos']

    def validate(self, data):
        if not data.get('lineas'):
            raise serializers.ValidationError('Debe incluir al menos una línea de pedido.')
        pagos = data.get('pagos', [])
        if pagos:
            total_pagos = sum(p['monto'] for p in pagos)
            if data['total_final'] != total_pagos:
                raise serializers.ValidationError(
                    f'La suma de los pagos (${total_pagos:.2f}) debe ser igual al total final (${data["total_final"]:.2f}).'
                )
        if data.get('descuento_porcentaje', 0) < 0 or data.get('descuento_porcentaje', 0) > 100:
            raise serializers.ValidationError('El descuento debe estar entre 0 y 100.')
        return data

    def create(self, validated_data):
        lineas_data = validated_data.pop('lineas')
        pagos_data = validated_data.pop('pagos')
        pedido = Pedido.objects.create(**validated_data)
        for linea_data in lineas_data:
            LineaPedido.objects.create(pedido=pedido, **linea_data)
        if pagos_data:
            for pago_data in pagos_data:
                Pago.objects.create(pedido=pedido, **pago_data)
            pedido.cerrado = True
            pedido.save(update_fields=['cerrado'])
        return pedido


class PedidoUpdateSerializer(serializers.ModelSerializer):
    lineas = LineaPedidoSerializer(many=True, required=False)

    class Meta:
        model = Pedido
        fields = ['subtotal', 'descuento_porcentaje', 'total_impuestos', 'total_final', 'lineas']

    def validate(self, data):
        if 'descuento_porcentaje' in data and (data['descuento_porcentaje'] < 0 or data['descuento_porcentaje'] > 100):
            raise serializers.ValidationError('El descuento debe estar entre 0 y 100.')
        return data

    def update(self, instance, validated_data):
        lineas_data = validated_data.pop('lineas', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if lineas_data is not None:
            instance.lineas.all().delete()
            for linea_data in lineas_data:
                LineaPedido.objects.create(pedido=instance, **linea_data)
        return instance
