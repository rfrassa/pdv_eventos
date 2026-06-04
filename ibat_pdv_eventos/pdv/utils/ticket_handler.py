import logging

from .local_printer import LocalPrinterService, ip_para_pdv
from .ticket_formatter import TicketFormatter

logger = logging.getLogger(__name__)


class TicketHandler:
    def __init__(self):
        self.formatter = TicketFormatter()

    def imprimir(self, pedido):
        ip = ip_para_pdv(pedido.punto_venta)
        if not ip:
            logger.warning(f"PDV {pedido.punto_venta.nombre} sin IP configurada ni en PDV_IMPRESORAS")
            return False

        printer = LocalPrinterService(ip=ip)
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
