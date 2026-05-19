import logging

from .local_printer import LocalPrinterService

logger = logging.getLogger(__name__)


class TicketHandler:
    def imprimir(self, pedido):
        ip = pedido.punto_venta.impresora_ip
        if not ip:
            logger.warning(f"PDV {pedido.punto_venta.nombre} sin IP de impresora configurada")
            return False

        printer = LocalPrinterService(ip=ip)
        try:
            printer.print_ticket(pedido)
            return True
        except Exception as e:
            logger.error(f"Error imprimiendo pedido #{pedido.id}: {e}")
            logger.info(f"Pedido #{pedido.id} guardado, ticket pendiente de reimpresión")
            return False


def imprimir_ticket(pedido):
    handler = TicketHandler()
    handler.imprimir(pedido)
