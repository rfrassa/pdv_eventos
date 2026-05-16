ANCHO_TICKET = 48


class TicketFormatter:
    def __init__(self, ancho=ANCHO_TICKET):
        self.ancho = ancho

    def _center(self, texto):
        return texto.center(self.ancho)

    def _left_right(self, izquierda, derecha):
        espacios = self.ancho - len(izquierda) - len(derecha)
        return izquierda + ' ' * espacios + derecha

    def _linea_sep(self, char='-'):
        return char * self.ancho

    def _wrap(self, texto, max_width=None):
        if max_width is None:
            max_width = self.ancho
        if len(texto) <= max_width:
            return [texto]
        palabras = texto.split()
        lineas = []
        linea_actual = ''
        for palabra in palabras:
            if len(linea_actual + ' ' + palabra) <= max_width:
                linea_actual = (linea_actual + ' ' + palabra).strip()
            else:
                lineas.append(linea_actual)
                linea_actual = palabra
        if linea_actual:
            lineas.append(linea_actual)
        return lineas

    def formatear(self, pedido, categoria_nombre=None, etiqueta=None, sufijo=None, mostrar_pagos=True):
        lineas = []
        evento = pedido.punto_venta.evento
        lineas.append(self._center('CENTRO DE ESTUDIANTES'))
        lineas.append(self._center('IBAT San José'))
        lineas.append('')
        lineas.append(self._center('Peña IBAT 2026'))
        lineas.append('')
        ticket_id = f"#{pedido.id}-{sufijo}" if sufijo else f"#{pedido.id}"
        lineas.append(self._left_right(f"PDV: {pedido.punto_venta.nombre}", ticket_id))
        lineas.append(self._left_right(pedido.creado.strftime('%d/%m/%Y %H:%M'), ''))
        if etiqueta:
            lineas.append(self._center(f'--- {etiqueta} ---'))
        lineas.append(self._linea_sep('='))
        lineas.append(self._left_right('PRODUCTO', 'TOTAL'))
        lineas.append(self._linea_sep('-'))

        subtotal_cat = 0
        impuestos_cat = 0
        for linea in pedido.lineas.all():
            if categoria_nombre and linea.producto.categoria.nombre != categoria_nombre:
                continue
            nombre = f"{linea.cantidad}x {linea.producto.nombre}"
            total_linea = float(linea.cantidad * linea.precio_unitario)
            subtotal_cat += total_linea
            tasa = float(linea.producto.tasa_impuesto)
            impuestos_cat += total_linea * tasa / 100
            precio_str = f"${total_linea:.2f}"
            for l in self._wrap(nombre):
                lineas.append(self._left_right(l, precio_str if l == nombre else ''))
                if l == nombre:
                    precio_str = ''
            if linea.nota:
                for l in self._wrap(f"  ({linea.nota})"):
                    lineas.append(l)

        if not any('x ' in l for l in lineas[self._find_lines_start(lineas):]):
            return lineas

        lineas.append(self._linea_sep('-'))
        total_cat = subtotal_cat + impuestos_cat

        if float(pedido.descuento_porcentaje) > 0 and categoria_nombre is None:
            lineas.append(self._left_right('Subtotal', f"${subtotal_cat:.2f}"))
            lineas.append(self._left_right(f"Descuento {pedido.descuento_porcentaje}%", ''))

        if categoria_nombre:
            lineas.append(self._left_right('Subtotal', f"${subtotal_cat:.2f}"))
            if impuestos_cat > 0:
                lineas.append(self._left_right('Impuestos', f"${impuestos_cat:.2f}"))
            lineas.append(self._linea_sep('='))
            tlinea = f'* TOTAL *  * ${total_cat:.2f} *'
            lineas.append(tlinea.rjust(self.ancho))
        else:
            lineas.append(self._linea_sep('='))
            tlinea = f'* TOTAL *  * ${pedido.total_final:.2f} *'
            lineas.append(tlinea.rjust(self.ancho))

        if mostrar_pagos:
            lineas.append(self._linea_sep('='))
            lineas.append('')
            lineas.append(self._center('-- PAGOS --'))

            for pago in pedido.pagos.all():
                if pago.monto_recibido and pago.monto_recibido > pago.monto:
                    vuelto = pago.monto_recibido - pago.monto
                    lineas.append(self._left_right(pago.get_metodo_display(), f"${pago.monto:.2f}"))
                    lineas.append(self._left_right('  Recibido', f"${pago.monto_recibido:.2f}"))
                    lineas.append(self._left_right('  Vuelto', f"${vuelto:.2f}"))
                elif pago.monto_recibido:
                    lineas.append(self._left_right(pago.get_metodo_display(), f"${pago.monto:.2f}"))
                    lineas.append(self._left_right('  Recibido', f"${pago.monto_recibido:.2f}"))
                else:
                    lineas.append(self._left_right(pago.get_metodo_display(), f"${pago.monto:.2f}"))

        lineas.append(self._linea_sep('='))
        lineas.append('')
        lineas.append(self._center('Gracias por su compra'))
        lineas.append(self._center('created by RaízDigital®'))
        lineas.append('')
        return lineas

    def _find_lines_start(self, lineas):
        for i, l in enumerate(lineas):
            if 'PRODUCTO' in l:
                return i + 1
        return 0
