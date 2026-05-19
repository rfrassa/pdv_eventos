import logging

from .local_printer import LocalPrinterService
from .ticket_formatter import TicketFormatter

logger = logging.getLogger(__name__)


class TicketHandler:
    def __init__(self):
        self.formatter = TicketFormatter()

    def imprimir(self, pedido):
        ip = pedido.punto_venta.impresora_ip
        if not ip:
            logger.warning(f"PDV {pedido.punto_venta.nombre} sin IP de impresora configurada")
            return False

        printer = LocalPrinterService()
        success = True

        try:
            printer.print_ticket(pedido)
        except Exception as e:
            logger.error(f"Error imprimiendo pedido #{pedido.id}: {e}")
            success = False

        if not success:
            logger.info(f"Pedido #{pedido.id} guardado, ticket pendiente de reimpresión")
        return success


def imprimir_ticket(pedido):
    handler = TicketHandler()
    handler.imprimir(pedido)
