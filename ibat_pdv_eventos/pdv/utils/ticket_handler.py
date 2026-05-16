import logging

from .printer_service import PrinterService
from .ticket_formatter import TicketFormatter

logger = logging.getLogger(__name__)

CAT_COMIDA = 'Comidas'
CAT_BEBIDA = 'Bebidas'


class TicketHandler:
    def __init__(self):
        self.formatter = TicketFormatter()

    def _categorias_en_pedido(self, pedido):
        return set(l.producto.categoria.nombre for l in pedido.lineas.all())

    def imprimir(self, pedido):
        ip = pedido.punto_venta.impresora_ip
        if not ip:
            logger.warning(f"PDV {pedido.punto_venta.nombre} sin IP de impresora configurada")
            return False

        categorias = self._categorias_en_pedido(pedido)
        printer = PrinterService(ip)
        success = True

        if CAT_COMIDA in categorias and CAT_BEBIDA in categorias:
            lineas = self.formatter.formatear(pedido, mostrar_pagos=True)
            success = printer.print_ticket(lineas) and success
            for cat, etiqueta, suf in [(CAT_BEBIDA, 'BEBIDAS', 'B'), (CAT_COMIDA, 'COMIDAS', 'C')]:
                lineas = self.formatter.formatear(pedido, categoria_nombre=cat, etiqueta=etiqueta, sufijo=suf, mostrar_pagos=False)
                success = printer.print_ticket(lineas) and success
        else:
            lineas = self.formatter.formatear(pedido, mostrar_pagos=True)
            success = printer.print_ticket(lineas)

        if not success:
            logger.info(f"Pedido #{pedido.id} guardado, ticket pendiente de reimpresión")
        return success


def imprimir_ticket(pedido):
    handler = TicketHandler()
    handler.imprimir(pedido)
