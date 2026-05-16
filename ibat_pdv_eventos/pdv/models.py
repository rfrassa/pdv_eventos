from django.db import models


class Evento(models.Model):
    nombre = models.CharField(max_length=200)
    fecha = models.DateField()
    activo = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'

    def __str__(self):
        return f"{self.nombre} ({self.fecha})"


class PuntoVenta(models.Model):
    nombre = models.CharField(max_length=100)
    impresora_ip = models.CharField(max_length=15, blank=True, null=True, verbose_name='IP de la impresora')
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='puntos_venta')

    class Meta:
        verbose_name = 'Punto de Venta'
        verbose_name_plural = 'Puntos de Venta'

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='categorias')

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    tasa_impuesto = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Tasa de impuesto (%)')
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='productos')
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='productos')
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['categoria__nombre', 'nombre']

    def __str__(self):
        return self.nombre


class Pedido(models.Model):
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.CASCADE, related_name='pedidos')
    creado = models.DateTimeField(auto_now_add=True)
    cerrado = models.BooleanField(default=False)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_impuestos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_final = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    veces_impreso = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-creado']

    def __str__(self):
        return f"Pedido #{self.id} - {self.punto_venta.nombre}"


class LineaPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    nota = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = 'Línea de Pedido'
        verbose_name_plural = 'Líneas de Pedido'

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre}"


class Pago(models.Model):
    METODOS = [
        ('EF', 'Efectivo'),
        ('TC', 'Tarjeta de crédito'),
        ('TD', 'Tarjeta de débito'),
        ('TR', 'Transferencia'),
        ('CU', 'Cuenta corriente'),
        ('OT', 'Otro'),
    ]
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pagos')
    metodo = models.CharField(max_length=2, choices=METODOS)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    monto_recibido = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Monto recibido')

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'

    def __str__(self):
        return f"{self.get_metodo_display()} ${self.monto}"
