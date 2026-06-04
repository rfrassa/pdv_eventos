from dataclasses import dataclass

ANCHO_TICKET = 48


@dataclass
class Segmento:
    texto: str
    alinear: str = 'left'    # 'left', 'center', 'right'
    negrita: bool = False
    doble_alto: bool = False

    def render_plano(self, ancho=ANCHO_TICKET):
        if self.alinear == 'center':
            return self.texto.center(ancho)
        if self.alinear == 'right':
            return self.texto.rjust(ancho)
        return self.texto


class TicketFormatter:
    def __init__(self, ancho=ANCHO_TICKET):
        self.ancho = ancho

    def _seg(self, texto, alinear='left', negrita=False, doble_alto=False):
        return Segmento(texto, alinear, negrita, doble_alto)

    def _sep(self, char='-'):
        return Segmento(char * self.ancho)

    def _left_right(self, izquierda, derecha, negrita=False):
        max_izq = self.ancho - len(derecha) - 1
        if len(izquierda) > max_izq:
            izquierda = izquierda[:max_izq]
        espacios = self.ancho - len(izquierda) - len(derecha)
        return Segmento(izquierda + ' ' * espacios + derecha, negrita=negrita)

    def _wrap(self, texto, max_width=None):
        if max_width is None:
            max_width = self.ancho
        if len(texto) <= max_width:
            return [texto]
        palabras = texto.split()
        lineas, linea_actual = [], ''
        for palabra in palabras:
            if len(linea_actual + ' ' + palabra) <= max_width:
                linea_actual = (linea_actual + ' ' + palabra).strip()
            else:
                lineas.append(linea_actual)
                linea_actual = palabra
        if linea_actual:
            lineas.append(linea_actual)
        return lineas

    def _encabezado(self, pedido, ticket_id, etiqueta=None):
        evento = pedido.punto_venta.evento
        segs = [
            self._seg('CENTRO DE ESTUDIANTES', 'center', negrita=True, doble_alto=True),
            self._seg('IBAT San Jose', 'center', negrita=True),
            self._seg(''),
            self._seg(evento.nombre, 'center', negrita=True, doble_alto=True),
            self._seg(''),
            self._left_right(f"PDV: {pedido.punto_venta.nombre}", ticket_id),
            self._left_right(pedido.creado.strftime('%d/%m/%Y %H:%M'), ''),
        ]
        if etiqueta:
            segs.append(self._seg(f'--- {etiqueta} ---', 'center', negrita=True))
        return segs

    def formatear_comanda(self, pedido, categoria_nombre, etiqueta, sufijo):
        segs = self._encabezado(pedido, f"#{pedido.id}-{sufijo}", etiqueta)
        segs.append(self._sep('='))

        items = []
        for linea in pedido.lineas.all():
            if linea.producto.categoria.nombre != categoria_nombre:
                continue
            nombre = f"{linea.cantidad}x {linea.producto.nombre}"
            for txt in self._wrap(nombre):
                items.append(self._seg(txt, negrita=True))
            if linea.nota:
                for txt in self._wrap(f"  ({linea.nota})"):
                    items.append(self._seg(txt))

        if not items:
            return []

        segs.extend(items)
        return segs

    def formatear(self, pedido, categoria_nombre=None, etiqueta=None, sufijo=None):
        ticket_id = f"#{pedido.id}-{sufijo}" if sufijo else f"#{pedido.id}"
        segs = self._encabezado(pedido, ticket_id, etiqueta)
        segs.append(self._sep('='))
        segs.append(self._left_right('PRODUCTO', 'TOTAL', negrita=True))
        segs.append(self._sep('-'))

        subtotal_cat = 0.0
        impuestos_cat = 0.0
        items = []
        for linea in pedido.lineas.all():
            if categoria_nombre and linea.producto.categoria.nombre != categoria_nombre:
                continue
            nombre = f"{linea.cantidad}x {linea.producto.nombre}"
            total_linea = float(linea.cantidad * linea.precio_unitario)
            subtotal_cat += total_linea
            tasa = float(linea.producto.tasa_impuesto)
            impuestos_cat += total_linea * tasa / 100
            precio_str = f"${total_linea:.2f}"
            partes = self._wrap(nombre)
            for i, txt in enumerate(partes):
                items.append(self._left_right(txt, precio_str if i == 0 else ''))
            if linea.nota:
                for txt in self._wrap(f"  ({linea.nota})"):
                    items.append(self._seg(txt))

        if not items:
            return []

        segs.extend(items)
        segs.append(self._sep('-'))
        total_cat = subtotal_cat + impuestos_cat

        if float(pedido.descuento_porcentaje) > 0 and categoria_nombre is None:
            segs.append(self._left_right('Subtotal', f"${subtotal_cat:.2f}"))
            segs.append(self._left_right(f"Descuento {pedido.descuento_porcentaje}%", ''))

        if categoria_nombre:
            segs.append(self._left_right('Subtotal', f"${subtotal_cat:.2f}"))
            if impuestos_cat > 0:
                segs.append(self._left_right('Impuestos', f"${impuestos_cat:.2f}"))
            segs.append(self._sep('='))
            total_txt = f'* TOTAL *  * ${total_cat:.2f} *'
        else:
            segs.append(self._sep('='))
            total_txt = f'* TOTAL *  * ${pedido.total_final:.2f} *'

        segs.append(self._seg(total_txt, 'right', negrita=True, doble_alto=True))
        segs.append(self._sep('='))
        segs.append(self._seg(''))
        segs.append(self._seg('-- PAGOS --', 'center', negrita=True))

        for pago in pedido.pagos.all():
            if pago.metodo == 'EF' and pago.monto_recibido:
                vuelto = pago.monto_recibido - pago.monto
                segs.append(self._left_right(pago.get_metodo_display(), f"${pago.monto:.2f}"))
                segs.append(self._left_right('  Recibido', f"${pago.monto_recibido:.2f}"))
                segs.append(self._left_right('  Vuelto', f"${vuelto:.2f}"))
            else:
                segs.append(self._left_right(pago.get_metodo_display(), f"${pago.monto:.2f}"))

        segs.append(self._sep('='))
        segs.append(self._seg(''))
        segs.append(self._seg('Gracias por su compra', 'center'))
        segs.append(self._seg('created by RaizDigital', 'center'))
        segs.append(self._seg(''))
        return segs
